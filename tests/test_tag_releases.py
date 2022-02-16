import pathlib
import time

import tag_releases

VALID_TEST_FILE="tests/test.toml"
INVALID_TEST_FILE="tests/invalid.toml"

class TestTagRelease:
    """
    Class to test tag_releases.py code
    """

    def test_ingest_config(self):
        """
        Test config ingestion
        :return: None
        """
        expected_config = [tag_releases.RepoInfo("test1", "develop", "develop1", "calver"),
                           tag_releases.RepoInfo("test2", "release", "release1", "semver",
                                                 "1.2.4rc2")]

        config = tag_releases.ingest_config(pathlib.Path(VALID_TEST_FILE))
        assert(config == expected_config)

    def test_generate_repo_url(self):
        """
        Test generate repo url code
        :return: None
        """
        config = tag_releases.ingest_config(pathlib.Path(VALID_TEST_FILE))
        repo_url = tag_releases.generate_repo_url(config[0])
        assert(repo_url == "https://api.github.com/repos/ssl-hep/test1")
        repo_url = tag_releases.generate_repo_url(config[1])
        assert(repo_url == "https://api.github.com/repos/ssl-hep/test2")

    def test_generate_calver(self):
        """
        Test calver generation
        :return: None
        """
        test_time = time.strptime("2022-02-16 09:18", "%Y-%m-%d %H:%M")
        assert(tag_releases.generate_calver(test_time) == "20220216-0918")

    def test_generate_tag(self):
        """
        Test tag generation
        :return: None
        """
        config = tag_releases.ingest_config(pathlib.Path(VALID_TEST_FILE))
        now = time.localtime()
        calver = f"{now.tm_year:04}{now.tm_mon:02}{now.tm_mday:02}-{now.tm_hour:02}{now.tm_min:02}"

        assert(tag_releases.generate_tag(config[0]) == f"{calver}-develop1")
        assert (tag_releases.generate_tag(config[1]) == "1.2.4rc2-release1")

    def test_verify_branch(self):
        """
        Test functionality to verify that a repo exists with the appropriate branch
        :return: None
        """
        config = tag_releases.ingest_config(pathlib.Path(VALID_TEST_FILE))
        assert(tag_releases.verify_branch(config[0]))
        assert(tag_releases.verify_branch(config[1]))
        config = tag_releases.ingest_config(pathlib.Path(INVALID_TEST_FILE))
        assert(not tag_releases.verify_branch(config[0]))
        assert(tag_releases.verify_branch(config[1]))

    def test_check_repos(self):
        """
        Test functionality to verify that a repo exists
        :return: None
        """
        config = tag_releases.ingest_config(pathlib.Path(VALID_TEST_FILE))
        assert(tag_releases.check_repos(config))
        config = tag_releases.ingest_config(pathlib.Path(INVALID_TEST_FILE))
        assert (not tag_releases.check_repos(config))
