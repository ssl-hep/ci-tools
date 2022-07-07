# ci-tools
Tools for CI testing

## tag_releases.py

This script will tag a set of repositories using the tags specified in a configuration
file. The script will require a github personal access token to tag the repository and
branch. The last commit in the specified branch will be tagged.  

### Options

| Option | Notes |
| ------ | ----- |
| --config | config file to use (default: `repos.toml`) |

### Configuration

`tag_releases.py` uses toml configuration files.  Each repo should be in a separate
section with named after the repo.  Settings are as follows:

```toml
[repository1-name]
branch = "develop" # branch to tag
label = "develop1" # label to add to tag e.g. 20220216-1307-develop1
tagtype = "calver" # use calendar versioning YYYYMMDD-HHMM

[repository2-name]
branch = "release"
label = "release1"
tagtype = "semver" # use semantic versioning
semver = "1.2.4rc2" # version tag to use

[repository3-name]
label = "integration"
tagtype = "calver" # use calendar versioning
commit =  "2b25c3f4223b402d153dc187087bd20e705d347f" # tag given commit

```

This config will tag the `develop` branch in `repository1-name` as
`YYYYMMDD-HHMM-develop1` (YYYYMMDD-HHMM will be replaced with current year, month, day,
hour, minute); the `release` branch in `repository2-name` as `1.2.4rc2-release1`; and commit
'2b25c3f4223b402d153dc187087bd20e705d347f' in `repository3-name` as `YYYYMMDD-HHMM-integration`.
*Note: if `branch` and `commit` are both specified, `commit` will be used instead of `branch`.

## retag_commit.py

This script will let a set of repos with a given tag be tagged with a different tag.  E.g.
if `repo1` and `repo2` have a tag called `20220218-1500-develop`, using this script will allow
the same code to be also be tagged as `20220220-1500-stable`.  This allows code to be tagged for
testing and then later tagged for a stable release.

### Options

| Option | Notes                                      |
| ------ |--------------------------------------------|
| --config | config file to use (default: `retag.toml`) |
| --debug | output debugging |

### Configuration

`retag_commit.py` uses toml configuration files.  Each tag should be in a separate
section with named after the tag.  Settings are as follows:

```toml
[tag1]
repos = "repo1,repo2,repo3" # repos to retag
label = "stable" # label to add to tag e.g. 20220216-1307-develop1
tagtype = "calver" # use calendar versioning YYYYMMDD-HHMM

[tag2]
repos = "repo4,repo5"
label = "release1"
tagtype = "semver" # use semantic versioning
semver = "1.2.4rc2" # version tag to use

```

This config will tag the code with the `tag1` tag in `repo1`, `repo2`, and `repo3` as
`YYYYMMDD-HHMM-stable` (YYYYMMDD-HHMM will be replaced with current year, month, day,
hour, minute); the code tagged as `tag2`  in `repo4` and `repo5` will also be tagged as
`1.2.4rc2-release1`.

# Releasing the Helm Chart
A second script is provided for publishing an updated version of the helm chart.
To invoke this script you need to cd into a local clone of this repo. When the
script is run, it will cd up one folder to verify that copies of the serviceX
and the ssl-helm-charts repos exist there. If they are not present, the script
will make a clone for you. Note that the script will check out the devel branch
of the ServiceX repo. If you happen to have local changes in your repo this will
cause problems.

To publish the chart all you need to do is issue this command:
```shell
./release_helm_chart.sh 20220621-1754-stable  1.0.31-RC.1
```
Where `20220621-1754-stable` is the generated calver for the latest set of
docker images. The script will reach out to DockerHub to make sure images have
been successfully published before moving on to the next step.

`1.0.31-RC.1` should be the semver for the desired chart version (Helm doesn't)
allow for calver in the chart versions.

## Script Actions in Brief
When the release_helm_chart is invoked it will do the following:
1. Insure that clones of the  serviceX and the ssl-helm-charts repos are
available
2. Verify that the docker images with the calver tag have all been published
to DockerHub
3. Checkout `develop` branch of ServiceX Repo
4. Update `Chart.yaml` to reflect the app version and the chart version
5. Update the default tags in `values.yaml` to point to the calver docker images
6. Commit and deploy to `develop` branch in ServiceX Repo
7. Update helm dependencies to match requirements.yaml
8. Create a helm chart package
9. Move the package to the ssl-helm-charts repo
10. Re-index that repo
11. Publish via gh-pages
