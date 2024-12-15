from typing import List
from typing import Dict, Any
from datetime import datetime
from fastapi import Depends, HTTPException
import logging

from celery import Celery
from database.database import SessionLocal
from fastapi import  Depends
from models.models import Manifests,dynamic_models
from sqlalchemy.orm import Session
from settings import settings




log = logging.getLogger()
log.setLevel('DEBUG')
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
log.addHandler(handler)




CELERY_BROKER_URL = settings.RABBITMQ_URL
CELERY_RESULT_BACKEND = "rpc://"

celery = Celery("opendive_tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)






@celery.task(name="celery_jobs.celery_tasks.process_data")  # Explicitly define task name
def process_data(data: str):
    """Sample task to process data"""
    print(f"Processing data: {data}")
    return f"Processed: {data}"


@celery.task(name="celery_jobs.celery_tasks.process_usl_data")  # Explicitly define task name
def process_usl_data(baselookup:str,  usl_data: Dict[str, Any]):
    """process data"""
    log.info("+++ process data +++")

    try:
        # db = get_db()
        db: Session = SessionLocal()  # Create session from SessionLocal()

        USLDictionaryModel = dynamic_models.get(baselookup)

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

    except Exception as e:
        log.info(f"++++++++ Worker failed. Error message: {e} +++++++++")
        raise HTTPException(status_code=500, detail=e)

        # return {"status":500, "message":e}