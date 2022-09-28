# library for git related functions

import os

import pygit2
from rich.console import Console
from rich.progress import Progress
import rich


class MyRemoteCallbacks(pygit2.RemoteCallbacks):

  def transfer_progress(self, stats):
    print(f'{stats.indexed_objects}/{stats.total_objects}')

class CloneCallbacks(pygit2.RemoteCallbacks):
  def __init__(self, credentials=None, certificate=None, console=None):
    """
    Init for callbacks
    :param credentials: ssh credentials
    :param certificate: tls certificate to use
    :param console: rich console to use for updates
    """
    super().__init__(credentials=credentials, certificate=certificate)
    if console is None:
      self.console = Console()
    else:
      self.console = console
    self.progress = None
    self.transferring = False
    self.transfer_task = None

  def start_progress(self) -> None:
    """
    Set up a progress bar for cloning progress updates
    :return: None
    """
    self.progress = Progress()

  def sideband_progress(self, string):
    """
    Progress output callback.  Override this function with your own
    progress reporting function

    Parameters:

    string : str
        Progress output from the remote.
    """
    self.console.print(string)

  def transfer_progress(self, stats) -> None:
    """
    Update git repo sync progress bar
    :param stats: stats from pygit2.clone_repository callback
    :return:  None
    """
    print(f"{stats.indexed_objects}/{stats.total_objects}")
    # if not self.transferring:
    #   print("Setup")
    #   self.transfer_task = self.progress.add_task("Syncing git objects...", total=stats.total_objects)
    # print("Update")
    # self.progress.update(self.transfer_task, advance=stats.indexed_objects)
    # print("Update done")

  def stop_progress(self) -> None:
    """
    Finish a progress bar for cloning progress updates
    :return: None
    """
    self.progress = None
    self.transferring = False
    self.transfer_task = None


def checkout_repo(repo_url: str, repo_dir: str = None,  console: rich.console.Console = None) -> pygit2.Repository | None:
  """
  Clone repository, exit with error message if something goes wrong
  :param repo_url: url to repository (e.g. https://github.com/ssl-hep/foo.git
  :param repo_dir: directory for  clone to go to
  :param console: optional rich Console to update
  """
  if console is None:
    console = Console()
  clone_callbacks = CloneCallbacks(console=console)
  console.print(f"Checking out {repo_url}")

  try:
    os.system(f"git clone {repo_url} {repo_dir}")
    repo = pygit2.Repository(repo_dir)
    # print(repo_dir)
    # clone_callbacks.start_progress()
    # print(type(clone_callbacks))
    # print(type(MyRemoteCallbacks()))
    # repo = pygit2.clone_repository(repo_url, repo_dir, callbacks=clone_callbacks)
    # repo = pygit2.clone_repository(repo_url, repo_dir, callbacks=MyRemoteCallbacks())
  except Exception as e:
    # if repo_dir:
    #   shutil.rmtree(repo_dir)
    print(f"exception {e}")
    return None
  finally:
    clone_callbacks.stop_progress()
  return repo


def add_file(repo: pygit2.Repository, add_file: str) -> bool:
  """
  Add a file to commit
  :param repo: repo being used
  :param add_file: path to file being added
  :return: True on success, False otherwise
  """
  cwd = os.getcwd()
  try:
    os.chdir(repo.workdir)
    exit_code = os.system(f"git add {add_file}")
    return exit_code == 0
  finally:
    os.chdir(cwd)


def checkout_branch(repo: pygit2.Repository, branch: str) -> bool:
  """
  Switch to specified branch in given repo
  :param repo: repo being used
  :param branch: name of branch to switch to
  :return: True on success, False otherwise
  """
  # ref = repo.lookup_branch(branch)
  # if not ref:
  #   print("no ref")
  #   return False
  # repo.checkout(ref)
  # return True
  # checking out the branch doesn't always work so use git directly for now
  cwd = os.getcwd()
  try:
    os.chdir(repo.workdir)
    exit_code = os.system(f"git switch {branch}")
    return exit_code == 0
  finally:
    os.chdir(cwd)


def commit(repo: pygit2.Repository) -> bool:
  """
  Probably should use pygit2 for this, but it adds a lot of work to
  get commit signing working correctly, so using git commit is easier
  :param repo: repo being used
  :return: True on success, False on failure
  """
  start_dir = os.getcwd()
  try:
    os.chdir(repo.workdir)
    exit_code = os.system("git commit")
    return exit_code == 0
  finally:
    os.chdir(start_dir)


def push(repo: pygit2.Repository) -> bool:
  """
  Push changes to origin
  :param repo: repo being used
  :return: True on success, False on failure
  """
  start_dir = os.getcwd()
  try:
    os.chdir(repo.workdir)
    exit_code = os.system("git push origin")
    return exit_code == 0
  finally:
    os.chdir(start_dir)

# testing workflow actions