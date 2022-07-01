# RepoInfo class used in various scripts

from dataclasses import dataclass

GITHUB_BASE_URL = "https://api.github.com"
GITHUB_ORGANIZATION = "ssl-hep"


@dataclass
class RepoInfo:
  name: str
  branch: str
  label: str
  tagtype: str
  semver: str = ""
  tag: str = ""
  commit: str = ""
  newtag: str = ""
  container_repo: str = ""
  container_registry: str = ""


def generate_repo_url(repo_config: RepoInfo) -> str:
  """
  Using repo_config get url for the repo
  :param repo_config: information for repo
  :return: url for the repo string
  """
  return f"{GITHUB_BASE_URL}/repos/{GITHUB_ORGANIZATION}/{repo_config.name}"


def container_url(repo_config: RepoInfo, tag) -> str:
  """
  Using repo_config get url for container image location
  :param repo_config: information for repo
  :param tag: string with tag for the container
  :return: url for the repo string
  """
  match repo_config.container_registry:
    case "dockerhub":
      return  f'https://hub.docker.com/v2/repositories/{repo_config.container_repo}/tags/{tag}'
    case "harbor":
      return f'https://hub.opensciencegrid.org/sslhep/{repo_config.container_repo}/tags/{tag}'
    case _:
      return ""
