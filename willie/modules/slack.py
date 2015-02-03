from collections import namedtuple
from configparser import ConfigParser

from slackclient import SlackClient
from willie import module
from willie.logger import get_logger

_Config = namedtuple('_Config', 'token users channels bot_name')
LOGGER = get_logger(__name__)
conf = None
slack_client = None


def configure(config):
    """
    | [slack] | example | purpose |
    | -------- | ------- | ------- |
    | oauth_token | xx-xx-xx-xx | The OAuth token to connect to the slack api |
    | slack_config_file | ~/.willie/slack_config.ini | user and channel maps
    """
    chunk = ''
    if config.option('Configuring slack channel mapping module', False):
        config.interactive_add('slack', 'oauth_token', 'Slack API token', '')
        config.interactive_add('slack', 'bot_name', 'bot suffix in slack',
                               'niku')
        config.interactive_add('slack', 'slack_config_file',
                               'abs_path_to_channel_map',
                               '~/.willie/slack_config.ini')
    return chunk


def _checkConfig(bot):
    config = ConfigParser()
    config.read(bot.config.slack.slack_config_file)

    if not config or 'USERS' not in config or 'CHANNELS' not in config:
        return False

    return _Config(bot.config.slack.oauth_token,
                   config['USERS'], config['CHANNELS'],
                   bot.config.slack.bot_name)


@module.commands('reload')
def reload(bot, trigger):
    if trigger.admin() or trigger.owner:
        setup(bot)
        bot.say('I just reloaded my positronic brain.')


@module.commands('amiaslacker')
def am_i_a_slacker(bot, trigger):
    if trigger.sender.is_nick():
        if trigger.nick in conf.users:
            bot.say('Ah, you slacker!')
        else:
            bot.say('Not that I know of')


@module.rule('.*')
def mirror(bot, trigger):
    if trigger.sender.is_nick():  # Don't map privmsg
        return

    line = trigger.group()
    if line.startswith("\x01ACTION"):  # For /me messages
        line = line[:-1]

    channel = conf.channels.get(trigger.sender[1:])
    if channel:
        _slack_send(channel, trigger.nick, line)
    else:
        LOGGER.debug('not logging message from %s' % trigger.sender)


def _slack_send(channel, identifier, line):
    if identifier in conf.users:
        slack_nick = '%s_%s' % (conf.users[identifier], conf.bot_name)
    else:
        slack_nick = '%s_irc' % identifier
    slack_line = _replace_irc_users(line)
    message = {'channel': '#%s' % channel,
               'link_names': '1',
               'token': conf.token,
               'text': slack_line,
               'username': slack_nick}
    status = slack_client.api_call('chat.postMessage', **message)
    LOGGER.info('message %r posted with status: %s' % (message, status))


def _replace_irc_users(line):
    output = []
    for word in line.split():
        if word in conf.users:
            output.append('@%s' % conf.users[word])
        elif word[:-1] in conf.users:
            output.append('@%s%s' % (conf.users[word[:-1]], word[-1]))
        else:
            output.append(word)
    return ' '.join(output)


def setup(bot):
    global conf
    global slack_client
    conf = _checkConfig(bot)
    slack_client = SlackClient(conf.token)
    #if not slack_client.rtm_connect():
        #raise IOError('Failed to connect to Slack')
