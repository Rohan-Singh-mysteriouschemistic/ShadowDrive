from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#username, password, hostname, DB
SQLALCHEMY_DATABASE_URL = "postgresql://user:SDrive516477#@localhost/shadowdrive"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()