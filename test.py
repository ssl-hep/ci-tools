import pathlib

import click


@click.command()
@click.option("--config", default="repos.toml", help="Configuration file for toml")
@click.option("--debug", default=False, help="Enable debugging")
@click.option("--tag", default=None, help="tag to check")
def tag(config: str, debug: bool, tag: str):
  print(f"tag with {config=} {bool=}")


@click.command()
@click.option("--config", default="repos.toml", help="Configuration file for toml",
              type=click.Path(exists=True, file_okay=True, dir_okay=False,
                              readable=True, path_type=pathlib.Path))
@click.option("--debug", default=False, help="Enable debugging")
@click.option("--tag", default=None, help="tag to chjeck")
def verify_containers(config: str, debug: bool, tag: str):
  print(f"verify_containers with {config=} {debug=} {tag=}")


@click.command()
@click.option("--config", default="repos.toml", help="Configuration file for toml")
@click.option("--debug", default=False, help="Enable debugging")
@click.option("--tag", default=None, help="tag to chjeck")
def verify_workflows(config: str, debug: bool, tag: str):
  print(f"verify_containers with {config=} {debug=} {tag=}")


@click.command(help="publish helm chart")
@click.option("--config", default="repos.toml", help="Configuration file for toml")
@click.option("--debug", default=False, help="Enable debugging")
@click.option("--tag", default=None, help="tag to chjeck")
def publish(config: str, debug: bool, tag: str):
  print(f"verify_containers with {config=} {debug=} {tag=}")


@click.group()
def entry() -> None:
  print("entry")

entry.add_command(verify_workflows)
entry.add_command(verify_containers)
entry.add_command(publish)
entry.add_command(tag)

if __name__ == "__main__":
  entry()
