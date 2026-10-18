import os
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

class TestRecord(Base):
    __tablename__ = 'test_records'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Metadata
    operator = Column(String(100))
    customer = Column(String(100))
    sample = Column(String(100))
    material = Column(String(100))
    standard = Column(String(100))
    
    # Dimensions
    width = Column(Float)
    thickness = Column(Float)
    gauge_length = Column(Float)
    
    # Results
    peak_load = Column(Float)
    peak_stress = Column(Float)
    
    # Raw Data Arrays (Stored as JSON string)
    time_data_json = Column(Text)
    load_data_json = Column(Text)
    ext_data_json = Column(Text)

class DBManager:
    def __init__(self, db_path="utm_data.db"):
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"Database initialized at {db_path}")

    def save_test(self, metadata: dict, results: dict, arrays: dict):
        """Saves a complete test record to the database."""
        session = self.Session()
        try:
            record = TestRecord(
                operator=metadata.get('operator', ''),
                customer=metadata.get('customer', ''),
                sample=metadata.get('sample', ''),
                material=metadata.get('material', ''),
                standard=metadata.get('standard', ''),
                
                width=metadata.get('width', 0.0),
                thickness=metadata.get('thickness', 0.0),
                gauge_length=metadata.get('gauge_length', 0.0),
                
                peak_load=results.get('peak_load', 0.0),
                peak_stress=results.get('peak_stress', 0.0),
                
                time_data_json=json.dumps(arrays.get('time', [])),
                load_data_json=json.dumps(arrays.get('load', [])),
                ext_data_json=json.dumps(arrays.get('ext', []))
            )
            session.add(record)
            session.commit()
            logger.info(f"Test record saved successfully. ID: {record.id}")
            return record.id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save test to DB: {e}")
            return None
        finally:
            session.close()

    def get_all_tests(self):
        """Returns basic info for all tests (for history table)."""
        session = self.Session()
        try:
            records = session.query(
                TestRecord.id, TestRecord.timestamp, TestRecord.operator, 
                TestRecord.material, TestRecord.peak_load, TestRecord.peak_stress
            ).order_by(TestRecord.id.desc()).all()
            return records
        finally:
            session.close()
