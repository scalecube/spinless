import time


def consume():
    while True:
        i = yield
        print("Consumed {}".format(i))

def produce(consumer):
    while True:
        data = time.time()
        print("Produced: {}", format(data))
        consumer.send(data)
        yield

consumer = consume()
consumer.send(None)
producer = produce(consumer)

for i in range(10):
    time.sleep(1)
    next(producer)