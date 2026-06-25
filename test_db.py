from sqlalchemy import create_engine
engine = create_engine('postgresql://user:SDrive516477%23@localhost/shadowdrive')
try:
    engine.connect()
except Exception as e:
    print(e)
