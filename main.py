import logging
import sqlite3
import sys
import datetime
from typing import List


def table_exists(conn, table_name) -> bool:
    """
    检查数据库中是否存在指定表
    :param conn: 数据库连接
    :param table_name: 表名
    :return:
    """
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
    table_exists = cursor.fetchone() is not None
    cursor.close()
    return table_exists


def task_status_update() -> None:
    """
    更新数据库中任务的完成状态
    :return:
    """
    # 遍历未完成的task，查询是否有未完成的todo，如果没有，则将task的完成状态设为已完成
    tasks = cur.execute("SELECT * FROM tasklist WHERE taskStatus = 0").fetchall()
    for task in tasks:
        todos = cur.execute("SELECT * FROM todolist WHERE taskNo = ? AND todoStatus = 0", (task[0],)).fetchall()
        if len(todos) == 0:
            cur.execute("UPDATE tasklist SET taskStatus = 1 WHERE taskNO = ?", (task[0],))
            conn.commit()
    return


def list_task_func(argv: List[str]) -> None:
    """
    检查进行中的任务
    :param argv: forgetrecall list
    :return:
    """
    # 查询为未完成状态并且日期在今天的todos，并进行格式化输出
    todos = cur.execute("SELECT * FROM todolist WHERE todoStatus = 0 AND todoDate = ?",
                        (datetime.date.today().strftime("%Y-%m-%d"),)).fetchall()
    for todo in todos:
        task = cur.execute("SELECT * FROM tasklist WHERE taskNO = ?", (todo[1],)).fetchone()
        print(f"{todo[0]}. {task[1]} - {task[2]}")
    return


def query_task_by_name_func(argv: List[str]) -> None:
    """
    查询任务
    :param argv: forgetrecall query <任务名>
    :return:
    """
    # 查询tasklist中任务名包含argv[0]的任务，并进行格式化输出
    tasks = cur.execute("SELECT * FROM tasklist WHERE taskName LIKE ?", (f"%{argv[0]}%",)).fetchall()
    for task in tasks:
        print(f"{task[0]}. {task[1]} - {task[2]}")
    return


def query_task_func(argv: List[str]) -> None:
    """
    查询任务
    :param argv: forgetrecall query
    :return:
    """
    # 查询所有未完成的task，并进行格式化输出
    tasks = cur.execute("SELECT * FROM tasklist WHERE taskStatus = 0").fetchall()
    for task in tasks:
        print(f"{task[0]}. {task[1]} - {task[2]}")
    return


def add_task_func(argv: List[str]) -> None:
    """
    创建新的任务
    :param argv: forgetrecall add <任务名> [任务描述] [间隔天数]
    :return:
    """
    # 检查是否存在数据表
    if not table_exists(conn, "tasklist"):
        cur.execute("CREATE TABLE tasklist (taskNO INTEGER PRIMARY KEY AUTOINCREMENT, taskName TEXT, taskDesc TEXT, "
                    "taskStatus INTEGER, taskStartDate TEXT)")

    if not table_exists(conn, "todolist"):
        cur.execute(
            "CREATE TABLE todolist (todoNo INTEGER PRIMARY KEY AUTOINCREMENT, taskNo INTEGER, todoDate TEXT, "
            "todoStatus INTEGER)")

    # 读取参数
    task_name = argv.pop(0)
    task_desc = task_name
    task_date = datetime.date.today()
    task_interval = [0, 1, 2, 4, 7, 15]
    if len(argv) > 0:
        task_desc = argv.pop(0)
    if len(argv) > 0:
        task_interval = [int(x) for x in argv]

    # 添加参数到数据库
    cur.execute("INSERT INTO tasklist (taskName, taskDesc, taskStatus, taskStartDate) VALUES (?, ?, 0, ?)",
                (task_name, task_desc, task_date.strftime("%Y-%m-%d")))

    task_id = cur.lastrowid
    # 插入事项
    now_date = datetime.date.today()
    for i in range(len(task_interval)):
        todo_date = now_date + datetime.timedelta(days=task_interval[i])
        cur.execute("INSERT INTO todolist (taskNo, todoDate, todoStatus) VALUES (?, ?, 0)",
                    (task_id, todo_date.strftime("%Y-%m-%d")))

    logging.info(f"任务 {task_name} 添加成功，内容：{task_desc}，日期：{task_interval}")

    conn.commit()
    return


def del_task_func(argv):
    """
    删除任务
    :param argv: forgetrecall delete <任务序号>
    :return:
    """
    # 根据任务序号删除对应的任务task
    task_no = argv.pop(0)
    task = cur.execute("SELECT * FROM tasklist WHERE taskNO = ?", (task_no,)).fetchone()
    if task is None:
        logging.error(f"任务 {task_no} 不存在")
        return
    # 删除该task下未完成的todos
    cur.execute("DELETE FROM todolist WHERE taskNo = ? AND todoStatus = 0", (task[0],))

    # 删除task
    cur.execute("DELETE FROM tasklist WHERE taskNO = ?", (task_no,))
    logging.info(f"任务 {task_no} 删除成功")
    return


def update_task_func(argv: List[str]) -> None:
    """
    修改任务
    :param argv: forgetrecall update <任务序号> [任务描述] [间隔天数]
    :return:
    """
    # 根据任务序号找到要修改的task，修改对应task的描述，并删除task下所有未完成的todos，按照新日期重新插入todos
    task_no = argv.pop(0)
    task = cur.execute("SELECT * FROM tasklist WHERE taskNO = ?", (task_no,)).fetchone()
    if task is None:
        logging.error(f"任务 {task_no} 不存在")
        return
    if len(argv) < 2:
        logging.error(f"任务 {task_no} 修改失败，缺少参数")
        return

    # 修改task的描述
    task_decs = argv.pop(0)
    if task_decs != 'KEEP':
        cur.execute("UPDATE tasklist SET taskDesc = ? WHERE taskNO = ?", (argv[1], task[0]))

    # 删除原来未完成的todos，重新添加未完成的todos
    task_interval = argv
    if task_interval[0] != "KEEP":
        task_interval = [int(x) for x in argv]

        # 删除task下所有未完成的todos，并根据task的开始日期重新添加todos
        cur.execute("DELETE FROM todolist WHERE taskNo = ? AND todoStatus = 0", (task[0],))
        now_date = datetime.date.today()
        start_date = datetime.datetime.strptime(task[3], "%Y-%m-%d").date()
        for i in range(len(task_interval)):
            todo_date = start_date + datetime.timedelta(days=task_interval[i])
            if todo_date < now_date:
                continue
            cur.execute("INSERT INTO todolist (taskNo, todoDate, todoStatus) VALUES (?, ?, 0)",
                        (task[0], todo_date.strftime("%Y-%m-%d")))

    logging.info(f"任务 {task_no} 修改成功，内容：{task_decs}，日期：{task_interval}")
    conn.commit()
    return


def recall_task_func(argv):
    """
    回顾任务
    将今日要完成的任务切换成已完成状态，
    如果输入了一个已经完成的今日任务，则会切换为未完成状态。
    :param argv: forgetrecall recall <todo序号>
    :return:
    """
    # 将todo序号的状态反转
    todo = cur.execute("SELECT * FROM todolist WHERE todoNo = ?", (argv[0],)).fetchone()
    if todo is None:
        logging.error(f"任务 {argv[0]} 不存在")
        return
    if todo[3] == 1:
        cur.execute("UPDATE todolist SET todoStatus = 0 WHERE todoNo = ?", (argv[0],))
    else:
        cur.execute("UPDATE todolist SET todoStatus = 1 WHERE todoNo = ?", (argv[0],))
    conn.commit()
    logging.info(f"任务 {argv[0]} 切换状态")
    return


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    argv: List[str] = sys.argv

    action = argv[1]

    if action == "list":
        list_task_func(argv[2:])
    elif action == "add":
        add_task_func(argv[2:])
    elif action == "delete":
        del_task_func(argv[2:])
    elif action == "update":
        update_task_func(argv[2:])
    elif action == "recall":
        recall_task_func(argv[2:])
    elif action == "query":
        query_task_by_name_func(argv[2:])

    task_status_update()

    conn.close()
