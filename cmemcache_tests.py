import pylibmc
import unittest
import pickle

class TestCmemcached(unittest.TestCase):

	def setUp(self):
		self.mc = pylibmc.Client(["127.0.0.1:11211"])
		#self.mc = pylibmc.Client(["127.0.0.1:11211","127.0.0.1:11212", "127.0.0.1:11213", "127.0.0.1:11214", "127.0.0.1:11215"])

	def testSetAndGet(self):
		self.mc.set("num12345", 12345)
		self.assertEqual(self.mc.get("num12345"), 12345)
		self.mc.set("str12345", "12345")
		self.assertEqual(self.mc.get("str12345"), "12345")

	def testDelete(self):
		self.mc.set("str12345", "12345")
		#delete return True on success, otherwise False
		ret = self.mc.delete("str12345")
		self.assertEqual(self.mc.get("str12345"), None)
		self.assertEqual(ret, True)

		ret = self.mc.delete("hello world")
		self.assertEqual(ret, False)

	def testGetMulti(self):
		self.mc.set("a", "valueA")
		self.mc.set("b", "valueB")
		self.mc.set("c", "valueC")
		result = self.mc.get_multi(["a", "b", "c", "", "hello world"])
		self.assertEqual(result, {'a':'valueA', 'b':'valueB', 'c':'valueC'})
	
	def testBigGetMulti(self):
		count = 10
		keys = ['key%d' % i for i in xrange(count)]
		pairs = zip(keys, ['value%d' % i for i in xrange(count)])
		for key, value in pairs:
			self.mc.set(key, value)
		result = self.mc.get_multi(keys)
		assert result == dict(pairs)

	def testFunnyDelete(self):
		result= self.mc.delete("")
		self.assertEqual(result, False)

	def testAppend(self):
		self.mc.delete("a")
		self.mc.set("a", "I ")
		ret = self.mc.append("a", "Do")
		print ret
		result = self.mc.get("a")
		print result
		self.assertEqual(result, "I Do")
		
	def testPrepend(self):
		self.mc.delete("a")
		self.mc.set("a", "Do")
		ret = self.mc.prepend("a", "I ")
		print ret
		result = self.mc.get("a")
		print result
		self.assertEqual(result, "I Do")

if __name__ == '__main__':
	unittest.main()

