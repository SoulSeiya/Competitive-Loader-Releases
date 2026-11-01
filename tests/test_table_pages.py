import time
import tkinter as tk
from tkinter import ttk
from unittest import TestCase,main,mock
from table_pages import TablePages
from challonge_shared import SharedBracketManager


class TablePageTests(TestCase):
    def test_all_rows_reachable_and_refresh_does_not_leak_rows(self):
        root=tk.Tk();root.attributes('-alpha',0);root.geometry('600x240')
        tree=ttk.Treeview(root,columns=('value',),show='headings',height=1)
        tree.pack(fill='both',expand=True);pages=TablePages(tree)
        try:
            for index in range(47):tree.insert('','end',iid=str(index),values=(index,))
            pages.capture();root.update()
            seen=set()
            for index in range(pages.pages()):
                pages.page=index;pages.render();seen.update(tree.get_children())
                self.assertLessEqual(len(tree.get_children()),pages.capacity)
            self.assertEqual(seen,{str(index) for index in range(47)})
            pages.reset();tree.delete(*tree.get_children())
            self.assertFalse(tree.exists('46'))
            tree.insert('','end',iid='new',values=('New',));pages.capture()
            self.assertEqual(tree.get_children(),('new',))
            self.assertEqual(pages.page,0)
        finally:root.destroy()

    def test_close_tournament_is_local_and_stops_the_review(self):
        manager=SharedBracketManager(None,None);manager.link='https://challonge.com/example'
        manager.snapshot={'id':'example'}
        with mock.patch('challonge_shared.SharedChallongeClient') as client:
            manager.submit('close')
            until=time.monotonic()+2
            while manager.version==0 and time.monotonic()<until:time.sleep(.01)
            manager.close();manager.thread.join(timeout=2)
            self.assertIsNone(manager.snapshot);self.assertEqual(manager.link,'')
            client.return_value.request.assert_not_called()


if __name__=='__main__':main()
