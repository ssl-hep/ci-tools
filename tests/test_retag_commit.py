import pathlib
import time

import pytest

import retag_commit

VALID_TEST_FILE = "tests/test-retag.toml"
INVALID_TEST_FILE = "tests/invalid-retag.toml"


class TestTagRelease:
    """
    Class to test retag_commit.py code
    """

    def test_ingest_config(self):
        """
        Test config ingestion
        :return: None
        """
        expected_config = [retag_commit.RepoInfo(name="repo1", label="stable", old_tag="tag1", tagtype="calver"),
                           retag_commit.RepoInfo(name="repo2", label="stable", old_tag="tag1", tagtype="calver"),
                           retag_commit.RepoInfo(name="repo3", label="release1", old_tag="tag2", tagtype="semver",
                                                 new_tag="1.2.4rc2"),
                           retag_commit.RepoInfo(name="repo4", label="release1", old_tag="tag2", tagtype="semver",
                                                 new_tag="1.2.4rc2"),
                           retag_commit.RepoInfo(name="repo5", label="develop", old_tag="tag3", tagtype="calver")]

        config = retag_commit.ingest_config(pathlib.Path(VALID_TEST_FILE))
        assert(config == expected_config)

    def test_generate_repo_url(self):
        """
        Test generate repo url code
        :return: None
        """
        config = retag_commit.ingest_config(pathlib.Path(VALID_TEST_FILE))
        repo_url = retag_commit.generate_repo_url(config[0])
        assert(repo_url == "https://api.github.com/repos/ssl-hep/repo1")
        repo_url = retag_commit.generate_repo_url(config[1])
        assert(repo_url == "https://api.github.com/repos/ssl-hep/repo2")

    def test_generate_calver(self):
        """
        Test calver generation
        :return: None
        """
        test_time = time.strptime("2022-02-16 09:18", "%Y-%m-%d %H:%M")
        assert(retag_commit.generate_calver(test_time) == "20220216-0918")

    def test_generate_tag(self):
        """
        Test tag generation
        :return: None
        """
        config = retag_commit.ingest_config(pathlib.Path(VALID_TEST_FILE))
        now = time.localtime()
        calver = f"{now.tm_year:04}{now.tm_mon:02}{now.tm_mday:02}-{now.tm_hour:02}{now.tm_min:02}"

        assert(retag_commit.generate_tag(config[0]) == f"{calver}-stable")
        assert (retag_commit.generate_tag(config[2]) == "1.2.4rc2-release1")

    def test_verify_commit(self):
        """
        Test functionality to verify that a commit exists within the repo
        :return: None
        """
        valid_config = retag_commit.RepoInfo(name="test1", label="stable", old_tag="20220216-1237-develop1",
                                             tagtype="calver")
        retag_commit.set_commit(valid_config)
        assert(valid_config.commit == "96a36e779da8f8074b8ab252c25d536a99f10645")
        assert(retag_commit.verify_commit(valid_config))
        invalid_config = retag_commit.RepoInfo(name="test1", label="stable", old_tag="20220216-1237-missing",
                                             tagtype="calver")
        with pytest.raises(SystemExit):
            retag_commit.set_commit(invalid_config)
        with pytest.raises(SystemExit):
            invalid_config.commit = "deadbeef"
            assert(not retag_commit.verify_commit(invalid_config))

    def test_check_repos(self):
        """
        Test functionality to verify that a repo exists
        :return: None
        """
        config1 = retag_commit.RepoInfo(name="test1", label="stable", old_tag="20220216-1237-develop1",
                              tagtype="calver")
        config2 = retag_commit.RepoInfo(name="test2", label="stable", old_tag="1.2.4rc2-release1",
                                        tagtype="calver")
        retag_commit.set_commit(config1)
        retag_commit.set_commit(config2)
        assert(retag_commit.check_repos([config1, config2]))
        config1.old_tag = "deadbeef"
        config1.commit = "deadbeef"
        assert (not retag_commit.check_repos([config1, config2]))
