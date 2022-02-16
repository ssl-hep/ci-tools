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
```

This config will tag the `develop` branch in `repository1-name` as 
`YYYYMMDD-HHMM-develop1` (YYYYMMDD-HHMM will be replaced with current year, month, day, 
hour, minute) and  the `release` branch in `repository2-name` as `1.2.4rc2-release1`