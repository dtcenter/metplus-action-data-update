#! /usr/bin/env python3

import sys
import os
import time
import shlex
import subprocess
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import dateutil.parser
import requests

# URL containing test data directories
WEB_DATA_DIR = 'https://dtcenter.ucar.edu/dfiles/code/METplus/test_data/'


def get_branch_name():
    branch_name = os.environ['INPUT_BRANCH_NAME']
    print(f"Input branch name: {branch_name}")

    # strip off -PR from end of branch name
    if branch_name.endswith('-PR'):
        branch_name = branch_name.rstrip('-PR')

    # strip off -ref from end of branch name
    if branch_name.endswith('-ref'):
        branch_name = branch_name.rstrip('-ref')

    print(f"Formatted branch name: {branch_name}")
    return branch_name


def get_data_info(branch_name):
    # Use dev DockerHub repo and develop branch data by default
    data_repo = os.environ['INPUT_DATA_REPO_DEV']
    data_version = 'develop'

    # search dir vX.Y for a main_vX.Y branch
    if branch_name.startswith('main_v'):
        if os.environ.get('INPUT_DATA_REPO_STABLE'):
            data_repo = os.environ.get('INPUT_DATA_REPO_STABLE')

        data_version = branch_name.lstrip('main_v')
    # search dir is branch name if feature branch data is used
    elif os.environ.get('INPUT_USE_FEATURE_DATA', 'false') != 'false':
        data_version = branch_name

    print(f"data repo: {data_repo}")
    print(f"data version: {data_version}")

    return data_repo, data_version

def get_search_url(data_version):
    version = f'v{data_version}' if data_version[0].isdigit() else data_version
    repo_name = os.environ['INPUT_REPO_NAME'].lstrip('dtcenter/')
    search_url = urljoin(WEB_DATA_DIR, repo_name)
    search_url = urljoin(search_url+'/', version)
    search_url = f"{search_url}/"
    return search_url

def get_tarfile_last_modified(search_url):

    search_string = os.environ['INPUT_DATA_PREFIX']
    print(f'\nLooking for tgz files that start with "{search_string}"\n'
          f'in {search_url}')

    dir_request = requests.get(search_url)

    # if it does not exist, exit script
    if dir_request.status_code != 200:
        print(f'\nURL does not exist: {search_url}\nExiting...')
        sys.exit(0)

    # get list of tar files from website
    soup = BeautifulSoup(requests.get(search_url).content,
                         'html.parser')
    tarfiles = [a_tag.get_text() for a_tag in soup.find_all('a')
                if a_tag.get_text().startswith(search_string) and
                a_tag.get_text().endswith('.tgz')]

    # get last modified time of each tarfile
    tarfile_last_modified = {}
    for tarfile in tarfiles:
        if sum(x.isdigit() for x in tarfile) > 7:
            print(f'(Filtering out {tarfile}: flagged as a duplicate)')
            continue

        tarfile_url = urljoin(search_url+'/', tarfile)
        last_modified = requests.head(tarfile_url).headers['last-modified']
        tarfile_last_modified[tarfile] = last_modified

    print("\nTARFILES:")
    if not tarfile_last_modified:
        print('**No tar files found**\n')
    for key, value in tarfile_last_modified.items():
        print(f"{key}\n  Last modified: {value}\n")

    return tarfile_last_modified


def docker_get_volumes_last_updated(data_version, data_repo):
    dockerhub_url = ('https://hub.docker.com/v2/repositories/'
                     f'dtcenter/{data_repo}/tags?name={data_version}')
    print(f'\nLooking for tags that start with "{data_version}"\n'
          f'in {dockerhub_url}')
    dockerhub_request = requests.get(dockerhub_url)
    if dockerhub_request.status_code != 200:
        print(f"Could not find DockerHub URL: {dockerhub_url}")
        return None

    volumes_last_updated = {}
    attempts = 0
    page = dockerhub_request.json()
    max_pages = int(os.environ['INPUT_TAG_MAX_PAGES'])
    print(f'Searching through maximum {max_pages} pages')
    while attempts < max_pages:
        results = page['results']
        for tag in results:
            tag_name = tag['name']
            if tag_name.startswith(data_version):
                volumes_last_updated[tag_name] = tag['last_updated']
        if not page['next']:
            break
        page = requests.get(page['next']).json()
        attempts += 1

    print("\nDATA VOLUMES:")
    if not volumes_last_updated:
        print('**No volumes found**\n')
    for key, value in volumes_last_updated.items():
        print(f"{key}\n  Last updated: {value}\n")

    return volumes_last_updated


def compare_tarfiles_to_volumes(data_version, tarfile_last_modified,
                                volumes_last_updated):
    # check status of each tarfile and add them to the
    # list of volumes to create if needed
    volumes_to_create = {}
    for tarfile, last_modified in tarfile_last_modified.items():
        category = os.path.splitext(tarfile)[0].split('-')[1]
        print(f"\nChecking tarfile: {category}")

        volume_name = f'{data_version}-{category}'
        # if the data volume does not exist, create it and push it to DockerHub
        if volume_name not in volumes_last_updated.keys():
            print(f'{volume_name} data volume does not exist.'
                  ' Creating data volume.')
            volumes_to_create[tarfile] = category
            continue

        # If data volume does exist, get last updated time of volume and
        # compare to tarfile last modified.
        # If any tarfile was modified after creation of
        # corresponding volume, recreate those data volumes
        volume_dt = dateutil.parser.parse(volumes_last_updated[volume_name])
        tarfile_dt = dateutil.parser.parse(last_modified)

        print(f"   Volume time: {volume_dt.strftime('%Y%m%d %H:%M:%S')}")
        print(f"  Tarfile time: {tarfile_dt.strftime('%Y%m%d %H:%M:%S')}")

        # if the tarfile has been modified more recently than the
        # data volume was created, recreate the data volume
        if volume_dt < tarfile_dt:
            print(f'{tarfile} has changed since {volume_name} was created. '
                  'Regenerating data volume.')
            volumes_to_create[tarfile] = category

    if not volumes_to_create:
        print("\nNo data volumes need to be created")
        sys.exit(0)

    return volumes_to_create

def get_mount_dict(search_url):
    mount_file = urljoin(search_url, 'volume_mount_directories')
    print(f'\nLooking for mount file: {mount_file}')

    mount_request = requests.get(mount_file)

    # if it does not exist, exit script
    if mount_request.status_code != 200:
        print(f'ERROR: URL does not exist: {mount_file}')
        sys.exit(1)

    lines = mount_request.content.splitlines()

    mount_dict = {}
    for line in lines:
        key, value = line.decode('utf-8').split(':', 1)
        mount_dict[key] = value

    return mount_dict

def create_data_volumes(volumes_to_create, search_url, data_repo,
                        data_version):
    mount_dict = get_mount_dict(search_url)

    data_dir = os.environ['INPUT_DOCKER_DATA_DIR']

    is_ok = True

    for tarfile, volume in volumes_to_create.items():
        if volume not in mount_dict:
            print(f"ERROR: {volume} not found in volume mounts file")
            is_ok = False
            continue

        docker_tag = f'{data_version}-{volume}'
        mount_pt = os.path.join(data_dir, mount_dict[volume]).rstrip('/')

        # build image
        cmd = (f'docker build -t dtcenter/{data_repo}:{docker_tag}'
               f' -f /docker/Dockerfile.data /docker'
               f' --build-arg TARFILE_URL={search_url}{tarfile}'
               f' --build-arg MOUNTPT={mount_pt}'
               f' --build-arg DATA_DIR={data_dir}')
        if not run_docker_command(cmd):
            is_ok = False
            continue

        # push image to DockerHub
        cmd = f'docker push dtcenter/{data_repo}:{docker_tag}'
        if not run_docker_command(cmd):
            is_ok = False
            continue

        # prune docker images to free disk space
        cmd = f'docker image prune -af'
        if not run_docker_command(cmd):
            is_ok = False
            continue

    if not is_ok:
        sys.exit(1)

def run_docker_command(cmd):
    print(f'\nRunning command: {cmd}')
    start_time = time.time()
    try:
        subprocess.run(shlex.split(cmd), check=True)
    except subprocess.CalledProcessError as err:
        print(f"ERROR: Command failed: {cmd} -- {err}")
        return False

    end_time = time.time()
    print("TIMING: Command took "
          f"{time.strftime('%M:%S', time.gmtime(end_time - start_time))}"
          f" (MM:SS): '{cmd}')")
    return True

def main():
    print(f"******\nRunning {__file__}\n*****\n")

    # ensure tag_max_pages action argument is an integer
    try:
        int(os.environ['INPUT_TAG_MAX_PAGES'])
    except ValueError:
        print('ERROR: Invalid value for tag_max_pages')
        sys.exit(1)

    branch_name = get_branch_name()

    data_repo, data_version = get_data_info(branch_name)

    search_url = get_search_url(data_version)

    # get last modified time of each tarfile
    tarfile_last_modified = get_tarfile_last_modified(search_url)

    volumes_last_updated = docker_get_volumes_last_updated(data_version,
                                                           data_repo)

    volumes_to_create = compare_tarfiles_to_volumes(data_version,
                                                    tarfile_last_modified,
                                                    volumes_last_updated)

    create_data_volumes(volumes_to_create,
                        search_url,
                        data_repo,
                        data_version)

    # write list of data volumes associated with branch to file
    print('Writing list of data volumes to /data_volumes.txt')
    with open('/data_volumes.txt', 'w') as file_handle:
        file_handle.write(','.join(volumes_last_updated))

    print(f"Success: {__file__}")

if __name__ == "__main__":
    main()
