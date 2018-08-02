# -*- coding:utf-8 -*-

"""
python线程池
此模块用于线程池的建立，主要包含类ThreadPool
支持等待所有任务完成但不结束线程，以使得后期可以继续增加任务并等待完成
结束线程时，可以阻塞知道线程全部结束，也可以直接返回，线程池
自行结束
"""


import threading
import random
import time

try:
    import queue
except:
    import Queue

class ThreadPool(object):
    """
    线程池实现
    典型用法:
    新建线程池，传入最大线程数量n：
    pool = ThreadPool(n)
    传入m个任务函数（可以不同）
    for i in range(m):
        func:任务函数
        args[0]:任务的list参数
        args[1]:任务的dict参数
        callback:任务函数运行完成后的回调函数
            callback(success, result)
            success:任务是否成功运行
            result:任务完成的返回值
        pool.put(func, args((),{}), callback)
    等待所有任务完成
    pool.wait()
    结束线程池
    pool.terminal()
    """
    def __init__(self, max_thread_num):
        #最大线程数量
        self._max_thread_num = max_thread_num
        #任务存放队列
        #数据类型为
        #(func1, args((),{}), func2)
        #func1:要运行的任务函数
        #args[0]:list参数解包
        #args[1]:dict参数解包
        #func2:任务执行完成后的回调函数
        #       arg1:任务完成成功标志
        #       arg2:任务完成返回值
        self._task_queue = queue.Queue()
        #线程列表，用于存放线程实例
        self._thread_list = []

        #terminal相关----------------
        #任务终止标志位
        #每次线程开始新的任务时，检查此标志位
        #True则表明调用了terminal方法，线程主动退出
        self._terminal_flag = False
        #实例化的线程数量，初始为最大值(因为构造函数中就实例化了所有线程)，
        #在调用terminal后，每结束一个线程就减一，当最后一个线程减一后，
        #此值变为0，此线程在结束前释放_terminal_event，使得terminal解阻塞
        self._thread_num = max_thread_num
        #用于操作_terminal_num的锁
        self._thread_num_lock = threading.Lock()
        #terminal阻塞event
        #当terminal方法使用阻塞模式时，使用此变量进行阻塞
        #同时每个线程结束自己时，利用_thread_num变量确定自己是不是最后一个
        #线程，如果是，则set此变量，使得terminal解阻塞
        self._terminal_event = threading.Event()
        
        #wait相关
        #空闲线程数量
        self._free_thread_num = 0
        #空闲线程数量操作锁
        self._free_thread_num_lock = threading.Lock()
        #已经调用了wait()
        self._wait_flag = False
        #wait阻塞event，原理同_terminal_event
        self._wait_event = threading.Event()
        
        #新建线程
        for i in range(max_thread_num):
            self._thread_list.append(threading.Thread(target = self._threadCall))
            self._thread_list[i].start()

    def _threadCall(self):
        """
        实际线程中运行的函数，这个函数不断在任务队列中获取任务运行
        """
        while True:
            #判断任务队列中是否有任务
            #有任务则取出任务，没有则表明此线程将成为空闲线程，将计数器加一
            self._free_thread_num_lock.acquire()
            if self._task_queue.qsize() > 0:
                freeFlag = False
                args = self._task_queue.get()
            else:
                freeFlag = True
                self._free_thread_num += 1
                #如果已经调用了wait，则通过判断_free_thread_num==max_thread_num
                #解除wait阻塞
                if self._wait_flag and self._free_thread_num == self._max_thread_num:
                    self._wait_event.set()
            self._free_thread_num_lock.release()
            
            if freeFlag:
                #上一步得出此线程空闲的结论后，在此处进行阻塞
                args = self._task_queue.get()
                #阻塞结束表明有任务运行，空闲计数器减一
                self._free_thread_num_lock.acquire()
                self._free_thread_num -= 1
                self._free_thread_num_lock.release()

            if self._terminal_flag:
            #终止标志表明要结束线程，则直接结束此线程
                self._thread_num_lock.acquire()
                self._thread_num -= 1
                self._thread_num_lock.release()
                if self._thread_num == 0:
                #如果这是最后一个线程，则解除_terminal_event阻塞
                    self._terminal_event.set()
                return

            #执行任务
            try:
                result = args[0](*args[1][0], **args[1][1])
                success = True
            except:
                result = None
                success = False
            if args[2]:
            #存在回调函数
                try:
                    args[2](success, result)
                except:
                    pass
            
    def put(self, func = None, args = (), callback = None):
        """
        向线程池中增加一个任务
        @func : 任务函数
        @args : 任务参数，args[0]是个list或tuple，包含普通参数，args[1]是个字典，包含关键字参数
        @callback : 任务完成后的回调函数,函数第一个参数为运行成功标志位，第二个参数为函数返回结果
        """
        if self._terminal_flag:
            return
        #将新任务加入队列
        self._task_queue.put((func, args, callback))

    def wait(self):
        """
        阻塞直到线程池中所有线程都空闲，即任务全部处理完毕，任务队列为空
        原理：wait函数使用_wait_event阻塞自己。每个线程在结束一个任务时，
        会检查是否还有任务，没有任务则会将空闲线程计数器加一，并在获取任务队列时阻塞自己。
        当最后一个非空闲线程处理完任务后，计数器数量会与最大线程数相同，
        此时这个线程解除_wait_event阻塞，进而wait阻塞结束
        """
        if (self._task_queue.qsize() > 0) or (self._free_thread_num != self._max_thread_num):
        #判断中的(self._task_queue.qsize() > 0)是必不可少的
        #当所有线程都处于空闲状态时，使用put增加任务后，立刻调用join会导致join失效
        #   pool = ThreadPool(5)
        #   pool.put(...)
        #   pool.join()
        #   这段代码在线程任务还未完成时可能就直接结束了
        #原因：
        #当所有线程空闲时，_free_thread_num = _max_thread_num
        #但是put()新任务进去后，_threadCall中的_task_queue.get()并不会立刻解除阻塞
        #（会有一个很小的延时）。此时任务队列非空，join不应该返回，
        #但_task_queue.get()由于延时依然阻塞，后续的_free_thread_num -= 1
        #不能得到执行，此时(self._free_thread_num != self._max_thread_num)判断的结果
        #是错误的，因此必须加上(self._task_queue.qsize() > 0),_task_queue.qsize()才是
        #线程闲的根本标志
        #当线程全部空闲时，没有线程能解除_wait_event的阻塞，所以仅凭
        #(self._task_queue.qsize() > 0)也是无法判断的
            self._wait_flag = True
            self._wait_event.clear()
            self._wait_event.wait()

    def terminal(self, block = True):
        """
        终止线程池
        线程终止使用_terminal_flag=True完成
        每次完成一个任务获取下一个任务时，即会判断_terminal_flag
        但是如果一个线程在获取任务队列的时由于队列空而阻塞的时候
        就会无法判断_terminal_flag,此时就需要向任务队列中插入一个
        无意义的对象用于解除阻塞,进而判断_terminal_flag
        block=True时terminal会阻塞，直到所有线程都退出才会返回
        否则直接返回
        阻塞原理同wait
        """
        self._terminal_flag = True
        for i in range(self._max_thread_num):
            self._task_queue.put(None)

        if block:
            self._terminal_event.wait()

    
if __name__ == '__main__':
    lock = threading.Lock()
    count = 0
    def call(arg):
        global count
        lock.acquire()
        print(count, end = ' ')
        count = count + 1
        print(arg)
        lock.release()
        time.sleep(random.randint(0,5))
        return arg

    def callback(flag, arg):
        print(' callback' + str(arg))

    pool = ThreadPool(4)
    for i in range(10):
        pool.put(call, [[i],{}], callback)
    print('put finished')
    pool.wait()
    print('start terminal')
    pool.terminal(False)
    print('end terminal')
        


