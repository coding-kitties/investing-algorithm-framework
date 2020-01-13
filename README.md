# Investing bot 

The investing bot is a free and open source investing bot written in Python. The goal is to give you a configurable bot 
where you can decide on how you implement your data providers, strategies, and brokers/exchanges. Also we want to allow 
you to let your bot facilitate multiple users.

It is designed to be controlled via Telegram. As of now, we are aiming to make the configuration of the different 
components by the use of plugins. Please see the documentation on how to make your own plugin.

### Disclaimer
This software is for educational purposes only. Do not risk money which you are afraid to lose. We can't stress this 
enough: BEFORE YOU START USING MONEY WITH THE BOT, MAKE SURE THAT YOU TESTED YOU STRATEGIES AND DATA PROVIDERS.  
USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS.

Always start by running a investing bot in Dry-run and do not engage money before you understand how it works and what profit/loss you should expect.

We strongly recommend you to have coding and Python knowledge, or trust the people that created the plugins your using. 
Do not hesitate to read the source code and understand the mechanism of this bot or the plugin you're using.

Brokers/Exchange marketplaces supported
------
Will be updated in the future 


Documentation
------
Will be updated in the future 
 
## Features

- [x] **Based on Python 3.6+**: Support for all operating systems - Windows, macOS and Linux.
- [x] **Persistence**: Persistence is achieved through sqlite.
- [ ] **Dry-run**: Run the bot without playing money.
- [ ] **REST API**: Manage the bot with the use of a REST API.
- [ ] **Backtesting**: Run a simulation of your buy/sell strategy.
- [ ] **Manageable via Telegram**: Manage the bot with Telegram.
- [ ] **Display profit/loss**: Display your profit/loss.
- [ ] **Daily summary of profit/loss**: Provide a daily summary of your profit/loss.
- [ ] **Performance status report**: Provide a performance status of your current trades.

## Quick start

The investing bot provides a Linux/macOS script to install all dependencies and help you to configure the bot.

The script will come as a future update

### Bot commands


```
usage: main.py [-h] [-V] [-c PATH]

Trading bot based on value principles

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  -c PATH, --config PATH
                        Specify configuration file (default: `config.json`).

```

### Telegram RPC commands

Telegram is not mandatory. However, this is a great way to control your bot.


## Development branches

The project is currently setup in two main branches:

- `develop` - This branch has often new features, but might also cause breaking changes.
- `master` - This branch contains the latest stable release. The bot 'should' be stable on this branch, and is generally well tested.
- `feature/*` - These are feature branches, which are being worked on heavily. Please don't use these unless you want to test a specific feature.
- `hotfix/*` - These are hot fix branches, which are being worked on heavily. Please don't use these unless you really need to.

## Support

### Help / Slack

For any questions not covered by the documentation or for further
information about the bot, we encourage you to join our slack channel.

[Slack](https://join.slack.com/t/investingbots/shared_invite/enQtODgwNTg3MzA2MjYyLTdiZjczZDRlNWJjNDdmYThiMGE0MzFhOTg4Y2E0NzQ2OTgxYjA1NzU3ZWJiY2JhOTE1ZGJlZGFiNDU3OTAzMDg)

### [Bugs / Issues](https://github.com/investingbots/value-investing-bot/issues?q=is%3Aissue)

If you discover a bug in the bot, please
[search our issue tracker](https://github.com/investingbots/value-investing-bot/issues?q=is%3Aissue)
first. If it hasn't been reported, please
[create a new issue](https://github.com/investingbots/value-investing-bot/issues/new) and
ensure you follow the template guide so that our team can assist you as
quickly as possible.

### [Feature Requests](https://github.com/investingbots/value-investing-bot/labels/enhancement)

Have you a great idea to improve the bot you want to share? Please,
first search if this feature was not [already discussed](https://github.com/investingbots/value-investing-bot/labels/enhancement).
If it hasn't been requested, please
[create a new request](https://github.com/investingbots/value-investing-bot/new)
and ensure you follow the template guide so that it does not get lost
in the bug reports.

### [Pull Requests](https://github.com/investingbots/value-investing-bot/pulls)

Feel like our bot is missing a feature? We welcome your pull requests!

Please read our
[Contributing document](https://github.com/investingbots/value-investing-bot/blob/develop/CONTRIBUTING.md)
to understand the requirements before sending your pull-requests.

**Note** before starting any major new feature work, *please open an issue describing what you are planning to do* or talk to us on [Slack](https://join.slack.com/t/investingbots/shared_invite/enQtODgwNTg3MzA2MjYyLTdiZjczZDRlNWJjNDdmYThiMGE0MzFhOTg4Y2E0NzQ2OTgxYjA1NzU3ZWJiY2JhOTE1ZGJlZGFiNDU3OTAzMDg). 
This will ensure that interested parties can give valuable feedback on the feature, and let others know that you are working on it.

**Important:** Always create your PR against the `develop` branch, not `master`.

## Requirements

### Uptodate clock
The clock must be accurate, syncronized to a NTP server very frequently to avoid problems with communication to the exchanges.

### Min hardware required

To run this bot we recommend you a cloud instance with a minimum of:

- Minimal (advised) system requirements: 2GB RAM, 1GB disk space, 2vCPU

In the future raspberry pi support will be added.

### Software requirements

- [Python 3.6.x](http://docs.python-guide.org/en/latest/starting/installation/)
- [pip](https://pip.pypa.io/en/stable/installing/)
- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- [virtualenv](https://virtualenv.pypa.io/en/stable/installation/) (Recommended)
- [Docker](https://www.docker.com/products/docker) (Recommended)