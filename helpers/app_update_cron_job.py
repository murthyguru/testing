from crontab import CronTab
import os
from logger import add_to_log
from flask_login import current_user
from datetime import datetime
####################### 

def get_dir_path():
  git_dir_path = '/home/operations/PV-DASH-RemoteUI'
  if os.path.exists(git_dir_path):
     add_to_log('cron job path', True, current_user.email, 'info', f" Path for Cronjob :{git_dir_path}")
     return git_dir_path
  current_file_path = os.path.abspath(__file__)
  file_path_list = current_file_path.split("/")
  file_path_list.pop()
  file_path_list.pop()
  file_path_without_file_name = "/".join(file_path_list)
  add_to_log('cron job path', True, current_user.email, 'info', f" Path for Cronjob :{file_path_without_file_name}")
  return file_path_without_file_name

def create_cron_job(TimeStamp,WeekDays):
    try:
        WeekDays = ','.join(WeekDays)
        minute  = TimeStamp.minute
        hours  = TimeStamp.hour
        # Create a new cron tab
        cron = CronTab(user=True)
        # Create a new cron job
        dir_path = str(get_dir_path())
        script_path = str(get_dir_path())+'/app_auto_update.py > /sos_data/app_update.log'
        job = cron.new(command= 'cd '+dir_path+' && python3 '+script_path, comment='app auto update')
        job.setall(f"{minute} {hours} * * {WeekDays}")
        # Write the cron job to the cron tab
        cron.write()
        print(f"\n\n Cron job Created Successfully")
        add_to_log('app auto update', True, current_user.email, 'info', f"Cron job Created Successfully")
    except Exception as e:
        print(f"Error occured while creating app update cron job :{e}")
        add_to_log('app auto update', False, current_user.email, 'warning', f"Error occured while creating app update cron job :{e}")


def remove_cron_job():
    try:
        # Initialize the CronTab object
        cron = CronTab(user=True)
        dir_path = str(get_dir_path())
        script_path = str(get_dir_path())+'/app_auto_update.py > /sos_data/app_update.log'
        for job in cron:
            if job.command == 'cd '+dir_path+' && python3 '+script_path or job.comment == 'app auto update':
                cron.remove(job)
        cron.write()
        print(f"\n\n Cron job Removed Successfully")
        add_to_log('app auto update', True, current_user.email, 'info', f"Cron job Removed Successfully")
    except Exception as e:
        print(f"Error occured while removing app update cron job :{e}")
        add_to_log('app auto update', False, current_user.email, 'warning', f"Error occured while removing app update cron job :{e}")
   
def create_app_update_command():
    try:
        # removes the existing cron jobs
        remove_manual_cron_job()
        # Create a new cron tab
        cron = CronTab(user=True)
        # Create a new cron job
        dir_path = str(get_dir_path())
        script_path = str(get_dir_path())+'/app_auto_update.py > /sos_data/app_update.log'
        job = cron.new(command= 'cd '+dir_path+' && python3 '+script_path, comment='app update now')
        job.setall(f"{datetime.today().minute+2} {datetime.today().hour} {datetime.today().day} {datetime.today().month} {datetime.today().weekday()}")
        # Write the cron job to the cron tab
        cron.write()
        add_to_log('app auto update', True, current_user.email, 'info', f"Cron job Created Successfully")
    except Exception as e:
        print(f"Error occured while creating app update cron job :{e}")
        add_to_log('app auto update', False, current_user.email, 'warning', f"Error occured while creating app update cron job :{e}")


def remove_manual_cron_job():
    try:
        # Initialize the CronTab object
        cron = CronTab(user=True)
        for job in cron:
            if job.comment == 'app update now':
                cron.remove(job)
        cron.write()
        add_to_log('Removed Existing CronJobs', True, current_user.email, 'info', f"Removed Manual update cronjob")
    except Exception as e:
        print(f"Error occured while removing app update cron job :{e}")
        add_to_log('app update', False, current_user.email, 'warning', f"Error occured while removing app update cron job :{e}")