import logging, json, time
logging.basicConfig(filename='logs/berta.log',level=logging.INFO,encoding='utf-8')
def event(name,data=None):
    logging.info(json.dumps({'time':time.time(),'event':name,'data':data},ensure_ascii=False))
