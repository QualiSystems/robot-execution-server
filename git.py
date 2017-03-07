# # must have Mercurial installed on Windows
#
# import hglib
# tag = 'tip'
# client = hglib.clone('https://bitbucket.org/tutorials/tutorials.bitbucket.org', 'schmo', updaterev=tag)
#
#

import git

d = 'schmo'
tag = '2.1.167'

c = git.Repo.clone_from('https://github.com/QualiSystems/cloudshell-cli', d)
g = git.Git(d)
g.checkout(tag)
