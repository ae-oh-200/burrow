from libraries import loggerdo, mailer, utils




class prevere():
	addr = None
	user = None
	password = None

	def __init__(self, config):
		self.addr = config['addr']
		self.user = config['user']
		self.password = config['password']
		self.sender = 'dale@mytuttle.com'
		loggerdo.log.debug("alerts object built")

	def shout(self, subject, message):
		loggerdo.log.debug("sending alert for {}".format(subject))
		mailer.reply(self.sender, subject, message, self.user, self.password, self.addr)

	def test(self):
		loggerdo.log.debug("alerts, test function")

		

