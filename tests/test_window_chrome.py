import unittest
from unittest.mock import Mock,patch
from window_chrome import apply_dark_titlebar


class WindowChromeTests(unittest.TestCase):
    def test_dark_mode_and_caption_use_native_handle(self):
        window=Mock();window.native.Handle.ToInt64.return_value=123
        dwm=Mock(return_value=0)
        with patch('window_chrome.ctypes.WinDLL',return_value=Mock(DwmSetWindowAttribute=dwm)):
            result=apply_dark_titlebar(window)
        self.assertEqual(result,{'dark':True,'caption_color':True})
        self.assertEqual([call.args[1] for call in dwm.call_args_list],[20,35,36])
        self.assertEqual(dwm.call_args.args[0],123)

    def test_windows_10_fallback_and_unsupported_caption_are_nonfatal(self):
        window=Mock();window.native.Handle.ToInt64.return_value=123
        dwm=Mock(side_effect=[1,0,1,1])
        with patch('window_chrome.ctypes.WinDLL',return_value=Mock(DwmSetWindowAttribute=dwm)):
            self.assertEqual(apply_dark_titlebar(window),{'dark':True,'caption_color':False})
        self.assertEqual([c.args[1] for c in dwm.call_args_list],[20,19,35,36])

    def test_missing_native_handle_keeps_application_usable(self):
        self.assertFalse(apply_dark_titlebar(object())['dark'])
