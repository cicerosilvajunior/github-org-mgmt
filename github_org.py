# coding=utf8
#

import json
import csv
from github import Github, NamedUser
from github import GithubException


class GithubOrganizationManager:
    __slots__ = []
    MIN_PREFIX_LENGTH = 3

    def __init__(self, config_file_name):
        self._config = self.read_config(config_file_name)
        self._github = Github(self._config['user'], self._config['password'])
        self._organization = \
            self._github.get_organization(self._config['organization'])

    def read_teams_from_csv(self, csvfile):
        """Read all teams and their users from the specified CSV file.
        A dictionary is returned with team names as key and a list of the team
        members (NamedUser objects) as values e.g.

        {'prj1': [alice, dan], 'prj2': [bob, cathy]}

        If a member does not exist, an exception is raised and the program
        aborts.
        """

        with open(csvfile) as userfile:
            userlist = csv.reader(userfile, delimiter=',')
            header = next(userlist, None)

            assert header.index('login') >= 0, \
                "CSV header should have a login field: %s" % header
            assert header.index('team') >= 0, \
                "CSV header should have a team field: %s" % header

            teams = {}

            for row in userlist:
                team_name = row[header.index('team')]
                login = row[header.index('login')]
                try:
                    user = self._github.get_user(login)

                    if(team_name not in teams):
                        # Add a new key to the teams dict, and
                        # add the first user to the member list
                        teams[team_name] = [user]
                    else:
                        # Append user name to existing team member list
                        teams[team_name].append(user)
                except GithubException:
                    print "%s,%s" % (login, team_name)

        return teams

    def read_config(self, config_file_name='ghorg.conf'):
        """Read the configuration from the specified file.
        The file should be in JSON format. See ‘ghorg.conf.example’.
        """
        try:
            with open(config_file_name) as config_file:
                config = json.load(config_file)
                return config
        except IOError:
            print ("Couldn't load configuration file ‘%s’. "
                   "Maybe you should create it?\n"
                   "See config.example for an example") % config_file_name
            raise SystemExit

    def add_teams_to_org(self, teams):
        """Adds the specified teams to the organization, including team
        members"""
        repo_config = self._config['repo_config']

        for team_name in teams.keys():
            print "^_^ %s ^_^" % team_name
            team = self._organization.create_team(team_name)
            team.edit(team_name, permission=self._config['repo_access'])
            repo = self._organization.create_repo(team_name, **repo_config)
            team.add_to_repos(repo)
            self.add_members_to_team(team, teams[team_name])

    def add_members_to_team(self, team, members):
        """Adds the members, a list of NamedUsers, to the team"""

        for member in members:
            print "    %s" % member.login
            self.__pygithub_add_membership(team, member)

    def __pygithub_add_membership(self, team, member):
        """
        :calls: `PUT /teams/:id/memberships/:user
          <http://developer.github.com/v3/orgs/teams>`_
        :param member: :class:`github.Nameduser.NamedUser`
        :rtype: None
        """
        assert isinstance(member, NamedUser.NamedUser), member
        headers, data = team._requester.requestJsonAndCheck(
            "PUT", team.url + "/memberships/" + member._identity
        )

    def delete_teams_from_org(self, prefix):
        """Delete all teams whose name starts with the specified prefix from
        the organization. This also deletes any repository with the same name
        as the team, if it exists. THIS CANNOT BE UNDONE!"""

        assert len(prefix) >= self.MIN_PREFIX_LENGTH, \
            ("Team name prefix is very short. This implies that a lot of teams"
             "may be deleted. Please use a prefix of at least %s characters") \
            % self.MIN_PREFIX_LENGTH

        teams_to_delete = self.get_teams_starting_with(prefix)

        if len(teams_to_delete) == 0:
            print "No teams start with %s, bailing out" % prefix
            return

        print '=' * 80
        print '!!! WARNING WARNING WARNING !!!'
        print "This deletes all teams starting with prefix %s" % prefix
        print 'and their repositories from the organization.'
        print '!!! THIS CANNOT BE UNDONE !!!'
        print '=' * 80
        print 'Teams to be deleted:'
        print ', '.join([team.name for team in teams_to_delete])
        print '=' * 80
        print 'Type in the prefix again to confirm: '

        choice = raw_input().lower()

        if choice != prefix:
            print 'Confirmation failed, bailing out.'
            return

        for team in teams_to_delete:
                print "Deleting %s" % team.name
                self.delete_team_repo_from_org(team.name)
                team.delete()

    def delete_team_repo_from_org(self, repo_name):
        """Delete the repository with the specified name from the organization.
        If the repository does not exist, a warning is printed"""

        try:
            repo = self._organization.get_repo(repo_name)
            repo.delete()
        except:
            print u"    Repo ‘%s’ already gone. Ignoring..." % repo_name

    def get_teams_starting_with(self, prefix):
        teams = []
        for team in self._organization.get_teams():
            if team.name.startswith(prefix):
                teams.append(team)
        return teams
