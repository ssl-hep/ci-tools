import pathlib
import time

import release_tool

VALID_TEST_FILE = "tests/test-tag.toml"
INVALID_TEST_FILE = "tests/invalid-tag.toml"


class TestTagRelease:
    """
    Class to test release_tool.py code
    """

    def test_ingest_config(self):
        """
        Test config ingestion
        :return: None
        """
        expected_config = [tag_releases.RepoInfo("test1", "develop", "develop1", "calver"),
                           release_tool.RepoInfo("test2", "release", "release1", "semver",
                                                 "1.2.4rc2")]

        config = release_tool.ingest_config(pathlib.Path(VALID_TEST_FILE))
        assert(config == expected_config)

    def test_generate_repo_url(self):
        """
        Test generate repo url code
        :return: None
        """
        config = release_tool.ingest_config(pathlib.Path(VALID_TEST_FILE))
        repo_url = release_tool.generate_repo_url(config[0])
        assert(repo_url == "https://api.github.com/repos/ssl-hep/test1")
        repo_url = release_tool.generate_repo_url(config[1])
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
        config = ci_tool.ingest_config(pathlib.Path(VALID_TEST_FILE))
        now = time.localtime()
        calver = f"{now.tm_year:04}{now.tm_mon:02}{now.tm_mday:02}-{now.tm_hour:02}{now.tm_min:02}"

        assert(tag_releases.generate_tag(config[0]) == f"{calver}-develop1")
        assert (tag_releases.generate_tag(config[1]) == "1.2.4rc2-release1")

    def test_update_branch_config(self):
        """
        Test functionality to verify that a repo exists with the appropriate branch
        :return: None
        """
        config = ci_tool.ingest_config(pathlib.Path(VALID_TEST_FILE))
        assert(release_tool.update_branch_config(config[0]))
        assert(config[0].commit == "96a36e779da8f8074b8ab252c25d536a99f10645")
        assert(release_tool.update_branch_config(config[1]))
        assert(config[1].commit == "8762caebb3b92955e6583b2eef5f7aaf4b277c57")
        config = release_tool.ingest_config(pathlib.Path(INVALID_TEST_FILE))
        assert(not release_tool.update_branch_config(config[0]))
        assert(not config[0].commit)
        assert(release_tool.update_branch_config(config[1]))
        assert(config[1].commit == "8762caebb3b92955e6583b2eef5f7aaf4b277c57")

    def test_verify_commit(self):
        """
        Test functionality to verify that a commit exists within the repo
        :return: None
        """
        config = tag_releases.ingest_config(pathlib.Path(VALID_TEST_FILE))
        config[0].commit = "96a36e779da8f8074b8ab252c25d536a99f10645"
        assert(release_tool.verify_commit(config[0]))
        config[1].commit = "deadbeef"
        assert(not ci_tool.verify_commit(config[1]))

    def test_check_repos(self):
        """
        Test functionality to verify that a repo exists
        :return: None
        """
        config = ci_tool.ingest_config(pathlib.Path(VALID_TEST_FILE))
        assert(release_tool.check_repos(config))
        config = release_tool.ingest_config(pathlib.Path(INVALID_TEST_FILE))
        assert (not ci_tool.check_repos(config))
