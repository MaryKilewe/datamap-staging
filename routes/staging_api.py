from fastapi import Depends, HTTPException

# from celery_jobs.celery_tasks import process_usl_data
from celery.result import AsyncResult
from sqlalchemy import text

from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict, Any
from datetime import datetime
import json
from fastapi import APIRouter
from typing import List
from uuid import UUID
import logging

from models.models import Manifests,Facility,dynamic_models
from database.database import get_database, SessionLocal, engine

log = logging.getLogger()
log.setLevel('DEBUG')
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
log.addHandler(handler)

router = APIRouter()





def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def check_table_exists(keyspace, collection_name, source_columns, db=Depends(get_db)):
    # If result has rows, the table exists
    if collection_name in db.list_collection_names():

        return True, None
    else:
        print(f"Table '{collection_name}' does not exist in database '{keyspace}'.")
        return False, f"Repository '{collection_name}' does not exist in staging '{keyspace}'."


class Manifest(BaseModel):
    manifest_id: UUID = Field(..., description="Manifest id for current data sent")
    usl_repository_name: str = Field(..., description="Name of  base repository being sent like Events, Immunizations etc")
    count: int = Field(..., description="Count of data extracted and sent from source")
    columns: List[str] = Field(..., description="Base repo column names")
    session_id: str = Field(..., description="Id of session for transmission")
    source_system_name: str = Field(..., description="Name of the system sending the data")
    source_system_version: str = Field(..., description="Version of the system sending the data")
    opendive_version: str = Field(..., description="Opendive version sending data")
    facility_name: str = Field(..., description="Facility name")
    facility_id: str = Field(..., description="Facility id")
    facility_country: str = Field(..., description="Facility country")
    facility_region: str = Field(..., description="Facility region")
    facility_organization: str = Field(..., description="Facility organization")



@router.post("/verify")
async def verify_manifest(manifest: Manifest, db: Session = Depends(get_db)):
    try:

        new_manifest = Manifests(
            manifest_id=manifest.manifest_id,
            facility_name=manifest.facility_name,
            facility_id=manifest.facility_id,
            usl_repository_name=manifest.usl_repository_name,
            expected_count=manifest.count,
            received_count=None,
            source_system_name=manifest.source_system_name,
            source_system_version=manifest.source_system_version,
            opendive_version=manifest.opendive_version,
            created_at=datetime.utcnow(),
            session_id=manifest.session_id,
            start=datetime.utcnow(),
            end=None,
        )
        db.add(new_manifest)
        db.commit()

        facilityExists = db.query(Facility).filter(Facility.facilityid == manifest.facility_id).first()
        if facilityExists:
            db.query(Facility).filter(Facility.facilityid == manifest.facility_id).update(
                {"facilityid":manifest.facility_id,
                 "facilityname":manifest.facility_name,
                "facilitycountry":manifest.facility_country,
                "facilityregion":manifest.facility_region})
            db.commit()
        else:
            new_facility = Facility(
                facilityid=manifest.facility_id,
                facilityname=manifest.facility_name,
                facilitycountry=manifest.facility_country,
                facilityregion=manifest.facility_region
            )
            db.add(new_facility)
            db.commit()

        # clear extracts under this facility
        from models.models import dynamic_models
        USLDictionaryModel = dynamic_models.get(manifest.usl_repository_name)

        if not getattr(USLDictionaryModel, "facilityid", None):
            log.info(f'------- Column does not exist : facilityid --------')
        db.query(USLDictionaryModel).filter(getattr(USLDictionaryModel, "facilityid", None) == manifest.facility_id).delete(synchronize_session=False)
        db.commit()  # Commit the changes

        log.info(f'++++++++ Cleared :{manifest.facility_id}({manifest.facility_name}) records from repository {manifest.usl_repository_name} +++++++++')

        return {"status": "Repository successfully verified"}

    except Exception as e:
        log.error("====== ERROR: verifying endpoint for base repository " + manifest.usl_repository_name + "===>",
                  e)
        raise HTTPException(status_code=500, detail=e)


@router.post('/usl/{baselookup}')
async def stage_usl_data(baselookup: str, data: Dict[str, Any], db=Depends(get_db)):
    try:
        log.info("+++ Started Staging +++")

        # update manifest
        # Manifests.objects(id=_id).update(end=datetime.utcnow(), receivedCount=10)
        # from celery_jobs.celery_tasks import process_usl_data

        task = process_usl_data(baselookup, data)
        print("+++ process_usl_data +++", task)

        task_id = task.id
        result = AsyncResult(task_id)

        log.info("+++ Staging results +++")
        # log.info({"task_id": task.id, "success": result.successful(), "results":  str(result.result) if result.successful() or result.failed() else None})
        log.info({"task_id": task.id, "success": task.success})

        # Check if the task is successful or failed
        if task.success:
            return {"status": 200, "task_id": task.id, "message": f"Successfully inserted {len(data['data'])} records"}
        else:
            return {"status": 500, "task_id": task.id, "message": f"Failed"}

        # return {"status":200, "message":f"Successfully inserted {len(inserts_result.inserted_ids)} records"}
    except Exception as e:
        return {"status": 500, "message": e}


def process_usl_data(baselookup:str,  usl_data: Dict[str, Any]):
    """process data"""
    log.info("+++ process data +++")

    try:
        # db = get_db()
        db: Session = SessionLocal()  # Create session from SessionLocal()

        USLDictionaryModel = dynamic_models.get(baselookup.lower())

        if not USLDictionaryModel:
            raise ValueError(f"Model for table '{baselookup}' not found.")
        log.info("+++ USLDictionaryModel +++", USLDictionaryModel)

        # Create multiple records then Add and commit the records to the database
        dataToBeInserted = usl_data["data"]
        new_records = [USLDictionaryModel(**data) for data in dataToBeInserted]

        db.add_all(new_records)
        db.commit()

        # Dynamically access the filter column
        column_attr = getattr(USLDictionaryModel, "facilityid", None)
        if not column_attr:
            raise ValueError(f"Column FacilityID not found in model '{baselookup}'.")

        count = db.query(USLDictionaryModel).filter(column_attr == usl_data["facility_id"]).count()

        db.query(Manifests).filter(Manifests.manifest_id == usl_data["manifest_id"]).update({"received_count": count})
        db.commit()  # Commit the changes

        if int(usl_data['batch_no']) == int(usl_data['total_batches']):
            db.query(Manifests).filter(Manifests.manifest_id == usl_data["manifest_id"]).update(
                {"end": datetime.utcnow()})
            db.commit()
        log.info(f"++++++++ Processed: {baselookup} USL data batch No. {usl_data['batch_no']} +++++++++")
        return {"task_id":"5357373", "success":True}

    except Exception as e:
        log.info(f"++++++++ Worker failed. Error message: {e} +++++++++")
        return {"task_id":"5357373", "success":False}


def convert_to_iso(value):
    try:
        # Try parsing the date string in common formats and convert to ISO
        parsed_date = datetime.strptime(value, "%d/%m/%Y")  # Example format: DD/MM/YYYY
        return parsed_date.isoformat()  # Convert to ISO format
    except ValueError:
        try:
            # Try another common date format
            parsed_date = datetime.strptime(value, "%Y-%m-%d")  # Example format: YYYY-MM-DD
            return parsed_date.isoformat()
        except ValueError:
            # If parsing fails, return the original value (it's not a date)
            return value


def convert_datetime_to_iso(data):
    if isinstance(data, dict):
        return {k: convert_datetime_to_iso(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_datetime_to_iso(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data


def convert_none_to_null(data):
    if isinstance(data, dict):
        return {k: convert_none_to_null(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_none_to_null(item) for item in data]
    elif data is None:
        return None  # This will be converted to null in JSON
    else:
        return data


def convert_datetime_to_iso(data):
    if isinstance(data, dict):
        return {k: convert_datetime_to_iso(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_datetime_to_iso(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data
