import re
import unittest

from helpers import SKILLS

REFERENCE_RE = re.compile(r"(?<![\w./-])references/[A-Za-z0-9_-]+\.md")
SIBLING_RE = re.compile(r"\.\./([A-Za-z0-9_-]+/[A-Za-z0-9_./-]+)")
SKILL_SCRIPT_RE = re.compile(r"<skill-dir>/(scripts/[A-Za-z0-9_./-]+)")
NAME_RE = re.compile(r"^name: (.+)$", re.MULTILINE)
DESCRIPTION_RE = re.compile(r"^description: (.+)$", re.MULTILINE)


def skill_dirs():
    return sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())


class SkillDocsTests(unittest.TestCase):
    def test_there_are_skills(self):
        self.assertGreater(len(skill_dirs()), 0)

    def test_frontmatter_matches_folder_and_has_description(self):
        for skill in skill_dirs():
            with self.subTest(skill=skill.name):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                name = NAME_RE.search(text)
                description = DESCRIPTION_RE.search(text)
                self.assertIsNotNone(name, "missing name")
                self.assertEqual(name.group(1).strip(), skill.name)
                self.assertIsNotNone(description, "missing description")
                self.assertLessEqual(len(description.group(1)), 1024)
                self.assertGreater(len(description.group(1)), 60, "description too short to trigger well")

    def test_reference_pointers_exist_in_their_own_skill(self):
        for skill in skill_dirs():
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            for ref in set(REFERENCE_RE.findall(text)):
                with self.subTest(skill=skill.name, ref=ref):
                    self.assertTrue((skill / ref).is_file(), f"{ref} missing")

    def test_sibling_pointers_resolve(self):
        for skill in skill_dirs():
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            for match in set(SIBLING_RE.findall(text)):
                path = match.rstrip("./")
                with self.subTest(skill=skill.name, pointer=path):
                    self.assertTrue((SKILLS / path).exists(), f"../{path} does not exist")

    def test_skill_scripts_exist(self):
        for skill in skill_dirs():
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            for path in set(SKILL_SCRIPT_RE.findall(text)):
                with self.subTest(skill=skill.name, script=path):
                    self.assertTrue((skill / path).is_file(), f"{path} missing")

    def test_every_skill_script_compiles(self):
        import py_compile
        for script_file in SKILLS.glob("*/scripts/*.py"):
            with self.subTest(script=script_file.name):
                py_compile.compile(str(script_file), doraise=True)


if __name__ == "__main__":
    unittest.main()
