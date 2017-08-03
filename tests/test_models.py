from tests import TestCaseBase
from core import models
import datetime

class Address(models.Model):
    type = models.StringProperty()  # E.g., 'home', 'work'
    street = models.StringProperty()
    city = models.StringProperty()
    is_active = models.BooleanProperty()


class TestModel(models.Model):
    name = models.StringProperty()
    title = models.StringProperty()
    jive = models.StringProperty(repeated=True)
    total = models.StringProperty()
    addresses = models.StructuredProperty(Address, repeated=True)
    data = models.JsonProperty()

    birthday = models.DateTimeProperty()
    # is_cool = models.BooleanProperty()
    # is_uncool = models.BooleanProperty()


def funco():
    pass


class SuperTest(TestCaseBase):
    def test_derp(self):
        m = TestModel(title='cheese', name='booger', total='666')
        m.title = 'cheese'
        m.jive = ['a', 's', 'd']

        m.addresses = [
            Address(city='MPLS'),
            Address(city='Barron')
        ]
        m.data = {'frog': funco}
        m.birthday = datetime.datetime.now()

        # raise Exception([m.name, m.jive, m.is_cool, m.is_uncool])
        # raise Exception([m.title, m.jive, m.total])
        self.assertEqual(m.title, 'cheese')
        self.assertEqual(m.jive, ['a', 's', 'd'])
        # self.assertEqual(m.is_cool, True)
        # self.assertEqual(m.is_uncool, False)
        # birthday - datetime.timedelta(hours=0)
        raise Exception(m._properties)
