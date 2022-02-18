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