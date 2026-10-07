import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import start


class LauncherTests(unittest.TestCase):
    def test_mac_downloads_and_linux_xdg(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with patch.object(start.platform, 'system', return_value='Darwin'), patch.object(Path, 'home', return_value=home):
                self.assertEqual(start.downloads_directory(), home / 'Downloads')
            (home / 'user-dirs.dirs').write_text('XDG_DOWNLOAD_DIR="$HOME/My Downloads"\n')
            with patch.object(start.platform, 'system', return_value='Linux'), patch.object(start.shutil, 'which', return_value=None), patch.object(Path, 'home', return_value=home), patch.dict(os.environ, {'XDG_CONFIG_HOME': temp}):
                self.assertEqual(start.downloads_directory(), home / 'My Downloads')

    def test_configuration_preserves_settings_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.env').write_text('# Keep this\nVESPERTAPE_API_PORT=8010\nVESPERTAPE_UID=old\n')
            with patch.object(start, 'ROOT', root), patch.object(start.platform, 'system', return_value='Darwin'):
                destination = start.configure(root / 'My Downloads' / 'VesperTape')
                first = (root / '.env').read_text()
                start.configure(destination)
                self.assertEqual(first, (root / '.env').read_text())
                self.assertTrue(destination.is_dir())
                self.assertIn('VESPERTAPE_API_PORT=8010', first)
                self.assertIn('VESPERTAPE_UID="10001"', first)
                self.assertNotIn('=old', first)
