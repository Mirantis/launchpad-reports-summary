from datetime import datetime, timedelta
from copy import deepcopy
from threading import RLock

def ttl_cache(seconds=0, minutes=0, hours=0, days=0):

    time_delta = timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days)

    def decorate(f):

        f._lock = RLock()
        f._updates = {}
        f._results = {}

        def do_cache(*args, **kwargs):

            lock = f._lock
            lock.acquire()

            try:
                key = (tuple([str(r) for r in args]), tuple(sorted(kwargs.items(), key=lambda i:i[0])))

                updates = f._updates
                results = f._results

                t = datetime.now()
                updated = updates.get(key, t)

                if key not in results or t-updated > time_delta:
                    # Calculate
                    updates[key] = t
                    result = f(*args, **kwargs)
                    results[key] = result
                    return result

                else:
                    # Cache
                    return results[key]

            finally:
                lock.release()

        return do_cache

    return decorate


if __name__ == "__main__":

    class T(object):

        i = 0;

        @ttl_cache(seconds=1)
        def expensive_func(self, c):
            self.i += 1
            return self.i

    import time

    t = T()

    for _ in xrange(50):
        time.sleep(.1)
        t1 = time.clock()
        print t.expensive_func('Dummy')
