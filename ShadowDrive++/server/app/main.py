from fastapi import FastAPI, Depends, status, HTTPException
from sqlalchemy.orm import Session
from . import models, schemas, utils
from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@app.post("/users", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email already registered"
        )
    
    hashed_password = utils.hash(user.password)
    
    new_user = models.User(
        username=user.username,
        email=user.email, 
        password_hash=hashed_password
    )

    db.add(new_user)      
    db.commit()           
    db.refresh(new_user)  
    
    return new_user