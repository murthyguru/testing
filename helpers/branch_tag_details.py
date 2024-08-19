import requests
import subprocess
import os
import configparser
from logger import add_to_log
from flask import jsonify
# Alex: Crashes my localhost, hard-coding current_user's email for now
from flask_login import current_user


def get_credential_from_gitconfig():
    try:
      # Get the gitconfig file.
      gitconfig_file = os.path.expanduser('/etc/gitconfig')

      # Get the token from the gitconfig file.
      with open(gitconfig_file) as f:
          config = configparser.ConfigParser()
          config.read_file(f)
          return config["credential"]
    except Exception as e:
       print(f"Exception  while fetching token from gitconfig- {e}")
       add_to_log('check for app update', False, 'operations@aderisenergy.com', 'warning', f"Exception  while fetching token from gitconfig- {e}")
       return None
    
def get_dir_path():
  git_dir_path = '/home/operations/PV-DASH-RemoteUI'
  if os.path.exists(git_dir_path):
     return git_dir_path
  current_file_path = os.path.abspath(__file__)
  file_path_list = current_file_path.split("/")
  file_path_list.pop()
  file_path_without_file_name = "/".join(file_path_list)
  return file_path_without_file_name

branch_name = "master"
repo_owner = 'solarops'
repo_name = 'PV-DASH-RemoteUI'
access_token = get_credential_from_gitconfig()['token'] if (get_credential_from_gitconfig() and 'token' in get_credential_from_gitconfig()) else None
cwd = get_dir_path()

def get_latest_tag_details():
  """Gets the details of a tag from a GitHub repository.

  Args:
    repo_owner: The owner of the GitHub repository.
    repo_name: The name of the GitHub repository.
    tag_name: The name of the tag.

  Returns:
    A JSON object containing the details of the tag.
  """
  
  url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/tags"
  response = None
  headers = {'Authorization': f'Bearer {access_token}'}
  try:

    response = requests.get(url, headers=headers)
    print(access_token)
  except Exception as e:
     print(f"Error while fetching latest tag from remote repo - {e}")
     add_to_log('check for app update', False, 'operations@aderisenergy.com', 'warning', f"Error while fetching latest tag from remote repo - {e}")
  if response and response.json():
    tag_list = [x['name'] for x in response.json()]
    tag_list = sorted(tag_list, key=lambda v: v.casefold())
    return tag_list[-1]
  return None


def get_current_tag_from_local():
    try:
      output = subprocess.check_output(['git','-C', str(cwd),'tag'],cwd=cwd)
      print(output)
      tags = []
      for line in output.decode('utf-8').splitlines():
          tags.append(line)
      tag = tags[-1] if tags else ''
      return tag
    except Exception as e:
       add_to_log('check for app update', False, 'operations@aderisenergy.com', 'warning', f"Error while fetching current tag {e}")
       return None


def get_tag_details():
  try:
      latest_tag = get_latest_tag_details()
      current_tag = get_current_tag_from_local()
      print(f" current_tag - {current_tag} ")
      print(f" latest_tag - {latest_tag} ")
      if(current_tag and latest_tag and latest_tag.casefold() > current_tag.casefold()):
          add_to_log('check for app update', True, 'operations@aderisenergy.com', 'info', f"  Update is Available  \n Current Version - {current_tag} \n Latest Version - {latest_tag} ")
          # return f"  Update is Available  \n Current Version - {current_tag} \n Latest Version - {latest_tag} "
          return jsonify({"status":"success","flag":True,"new_version":latest_tag,"current_version":current_tag})
      else:
          add_to_log('check for app update', True, 'operations@aderisenergy.com', 'info', "Already up to date, No update is available")
          # return "Already up to date, No update is available"
          return jsonify({"status":"success","flag":False,"new_version":latest_tag,"current_version":current_tag})
  except Exception as e:
     add_to_log('check for app update', False, 'operations@aderisenergy.com', 'warning', f"Error while fetching latest tag {e}")
     return jsonify({"status":"failure","message":f"Error {e}"})
    #  return f"Please try again later, Error: {e}"


def get_github_release_data(tag):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/tags/{tag}"

    headers = {}
    if access_token:
        headers['Authorization'] = f"Bearer {access_token}"

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to retrieve release data. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error making a request to GitHub: {e}")
        return None
      
def check_for_update():
  try:
      latest_tag = get_latest_tag_details()
      current_tag = get_current_tag_from_local()
      if(current_tag and latest_tag and latest_tag.casefold() > current_tag.casefold()):
          return jsonify({"status":"success","flag":True,"new_version":latest_tag,"current_version":current_tag})
      else:
          return jsonify({"status":"success","flag":False,"new_version":latest_tag,"current_version":current_tag})
  except Exception as e:
     return jsonify({"status":"failure","message":f"Error {e}"})