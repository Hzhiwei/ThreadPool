python线程池此模块用于线程池的建立，主要包含类ThreadPool支持等待所有任务完成但不结束线程，以使得后期可以继续增加任务并等待完成。结束线程时，可以阻塞直到线程全部结束，也可以直接返回，线程池自行结束。
##Usage：
```
#新建线程池，传入最大线程数量n：
pool = ThreadPool(n)
#传入m个任务函数（可以不同）
for i in range(m):
'''
func:任务函数
args[0]:任务的list参数
    args[1]:任务的dict参数
    callback:任务函数运行完成后的回调函数
        callback(success, result)
        success:任务是否成功运行
        result:任务完成的返回值
'''
    pool.put(func, args((),{}), callback)
#等待所有任务完成
pool.wait()

#上面的传入任务，等待任务完成的过程可以不断重复
#每次pool.wait()时会阻塞直到put()进去的任务全部完成

#结束线程池
pool.terminal()
```

