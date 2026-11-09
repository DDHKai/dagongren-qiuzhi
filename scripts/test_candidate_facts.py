import unittest
from candidate_facts import extract_facts

class FactTests(unittest.TestCase):
    def test_stable_local_ids_and_private_salt(self):
        resume={'experiences':[{'responsibilitiesRaw':'合成示例任务'}]}
        first=extract_facts(resume,b'local-a','source')
        self.assertEqual(first,extract_facts(resume,b'local-a','source'))
        self.assertNotEqual(first[0]['id'],extract_facts(resume,b'local-b','source')[0]['id'])
        self.assertNotIn('合成',first[0]['id'])
    def test_edit_changes_evidence_identity(self):
        a=extract_facts({'experiences':[{'responsibilitiesRaw':'合成任务一'}]},b'a','s')
        b=extract_facts({'experiences':[{'responsibilitiesRaw':'合成任务二'}]},b'a','s')
        self.assertNotEqual(a[0]['id'],b[0]['id'])

if __name__=='__main__':unittest.main()
