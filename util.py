import glob
import os
import pathlib
import shutil
import time

import toml
import yaml

from repoinfo import RepoInfo
from error_handling import error, warn


def ingest_config(config_file: pathlib.Path) -> list[RepoInfo]:
  """
  Ingest configuration information

  :param config_file: name of file with configuration
  :return: dictionary with repo information (key -> dict with repo values)
  """
  parsed = toml.load(config_file)
  repos = []
  for key in parsed.keys():
    branch = None
    label = ""
    tagtype = ""
    commit = ""
    semver = ""
    container_repo = ""
    container_registry = ""
    for setting in ['branch', 'label', 'tagtype', 'commit', 'container_repo', 'container_registry']:
      match setting:
        case 'branch': branch = parsed[key][setting]
        case 'label': label = parsed[key][setting]
        case 'tagtype':
          tagtype = parsed[key][setting].lower()
          if tagtype == 'semver':
            semver = parsed[key]['semver']
        case 'commit':
          if 'commit' in parsed[key]:
            commit = parsed[key][setting].lower()
        case 'container_repo':
          if 'container_repo' in parsed[key]:
            container_repo = parsed[key][setting].lower()
        case 'container_registry':
          if 'container_registry' in parsed[key]:
            container_registry = parsed[key][setting].lower()
        case _: warn(f"Unknown setting {setting} in section {key}")
    if branch is None:
      error(f"Section {key} missing branch setting")
    if label is None:
      error(f"Section {key} missing label setting")
    if tagtype is None:
      error(f"Section {key} missing tagtype setting")
    if tagtype not in ['semver', 'calver']:
      error(f"In section {key}, tagtype must be 'semver' or 'calver', got {tagtype}")
    if branch and commit:
      warn(f"In section {key}, branch and commit both set, using commit")
    repos.append(RepoInfo(name=key, branch=branch, label=label,
                          tagtype=tagtype, semver=semver, commit=commit,
                          container_repo=container_repo, container_registry=container_registry))
  return repos


def generate_calver(date: time.struct_time = None) -> str:
  """
  Generate and return a calver (YYYYMMDD-HHMM)
  :param date: optional date
  :return: string with calver
  """
  if date:
    target_date = date
  else:
    target_date = time.gmtime()
  return f"{target_date.tm_year:04}{target_date.tm_mon:02}{target_date.tm_mday:02}-" \
         f"{target_date.tm_hour:02}{target_date.tm_min:02}"


def replace_tags(file_path: pathlib.Path, new_tag: str) -> None:
  """
  Replace given tag in a values.yaml file with a new tag,
  :param file_path: path to values.yaml file
  :param new_tag: new tag to use
  :return: None
  """
  if not file_path.is_file():
    return
  with file_path.open() as f:
    values = yaml.load(f, yaml.SafeLoader)
    for section in ['app', 'didFinder', 'CERNOpenData', 'codeGen', 'x509Secrets']:
      if section in values and 'tag' in values[section]:
        values[section]['tag'] = new_tag
    if 'transformer' in values and 'defaultTransformerTag' in values['transformer']:
      values['transformer']['defaultTransformerTag'] = new_tag
  new_file = file_path.with_name("values.yaml.new")
  yaml.safe_dump(values, new_file.open('w'))
  new_file.replace(file_path)


def replace_appver(file_path: pathlib.Path, new_tag: str, release_version: str) -> None:
  """
  Replace the app version with a new value
  :param file_path: path to Chart.yaml file
  :param new_tag: new tag to use
  :param release_version: release version of the chart
  :return: None
  """
  if not file_path.is_file():
    return
  with file_path.open() as f:
    values = yaml.load(f, yaml.SafeLoader)
    if 'appVersion' in values:
      values['appVersion'] = new_tag
    if 'version' in values:
      values['version'] = release_version
  new_file = file_path.with_name("Chart.yaml.new")
  yaml.safe_dump(values, new_file.open('w'))
  new_file.replace(file_path)


def generate_helm_package(chart_dir: pathlib.Path, chart_repo_dir: pathlib.Path) -> None:
  """
  Update and generate a helm chart archive for ServiceX
  :param chart_dir: directory with helm charts for ServiceX (should be the ssl-helm repo)
  :param chart_repo_dir directory with all the prior helm charts for ServiceX
  :return: None
  """
  if not chart_dir.is_dir() or not chart_repo_dir.is_dir():
    return
  cur_dir = os.getcwd()
  try:
    os.chdir(chart_dir)
    if os.system("helm dependency update servicex") != 0:
      error("Can't update helm dependencies for ServiceX")
    if os.system("helm package servicex") != 0:
      error("Can't generate ServiceX package archive")
    for archive in glob.glob("servicex-*.tgz"):
      print(f"moving {archive} to {chart_repo_dir / archive}")
      print(f"{chart_repo_dir}")
      shutil.move(archive, chart_repo_dir / archive)
    os.chdir(chart_repo_dir)
    if os.system("helm repo index . --url https://ssl-hep.github.io/ssl-helm-charts/") != 0:
      error("Can't update chart index")
    os.system
  finally:
    os.chdir(cur_dir)


