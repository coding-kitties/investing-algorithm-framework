[![Build Status](https://travis-ci.org/investingbots/investing-bot-framework.svg?branch=master)](https://travis-ci.org/investingbots/investing-bot-framework)

# Investing Algorithm Framework

The Investing Algorithm Framework is a free and open source Python framework that encourages rapid development and clean, 
pragmatic design.

The goal is to give you a configurable investing algorithm where you can decide how you implement your data providers, 
strategies, and order executors.

#####Disclaimer
If you use this framework for your investments, do not risk money which you are afraid to lose. We can't stress this 
enough: 

BEFORE YOU START USING MONEY WITH THE FRAMEWORK, MAKE SURE THAT YOU TESTED YOUR COMPONENTS THOROUGHLY. USE THE SOFTWARE AT 
YOUR OWN RISK. THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR INVESTMENT RESULTS.

Also, make sure that you read the source code of any plugin you use or implementation of an algorithm made with this 
framework.

Documentation
------
All documentation is in the "docs" directory and online at "". If you're just getting started, here's how we recommend 
you read the docs:

* First, read install for instructions on installing Investing Algorithm Framework.
* Next, work through the tutorials in order. ("Quickstart", "Template algorithm", "Custom algorithm").
* For concrete algorithm examples you probably want to read through the topical guides.
 

## Development branches

The project is currently setup in two main branches:

- `develop` - This branch has often new features, but might also cause breaking changes.
- `master` - This branch contains the latest stable release. The bot 'should' be stable on this branch, and is generally well tested.
- `feature/*` - These are feature branches, which are being worked on heavily. Please don't use these unless you want to test a specific feature.
- `hotfix/*` - These are hot fix branches, which are being worked on heavily. Please don't use these unless you really need to.


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