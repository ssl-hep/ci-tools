import pathlib
import time

import toml

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
