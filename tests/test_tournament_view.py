import copy
import json
from pathlib import Path
import tkinter as tk
import unittest
from tournament_view import TournamentView
from battle_hub import ORANGE


class TournamentViewTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.attributes('-alpha',0);self.root.geometry('980x650')
        self.view=TournamentView(self.root);self.view.pack(fill='both',expand=True);self.root.update()
        path=Path(__file__).resolve().parent/'fixtures/challonge_public_tournament.json'
        self.snapshot=json.loads(path.read_text(encoding='utf-8'))

    def tearDown(self):
        for callback in self.root.tk.call('after','info'):
            command=self.root.tk.call('after','info',callback)[0]
            def owner(widget):
                if command in (widget._tclCommands or []):return widget
                for child in widget.winfo_children():
                    result=owner(child)
                    if result:return result
            (owner(self.root) or self.root).after_cancel(callback)
        self.root.destroy()

    def test_existing_bracket_full_names_and_details(self):
        self.view.render(self.snapshot)
        self.assertEqual(len(self.snapshot['participants']),10)
        first=self.snapshot['matches'][0]
        items=self.view.canvas.find_withtag('match:'+first['id'])
        texts=[self.view.canvas.itemcget(item,'text') for item in items if self.view.canvas.type(item)=='text']
        self.assertIn(first['id'],self.view.visible_match_ids)
        self.view.choose(first['id'])
        self.assertIn(first['name1'],self.view.detail.get())
        self.assertIn(first['scores'],self.view.detail.get())
        self.assertEqual(str(self.view.tabs['losers'].cget('state')),'disabled')

    def test_losers_zoom_unicode_and_preserved_scores(self):
        snapshot=copy.deepcopy(self.snapshot)
        match=copy.deepcopy(snapshot['matches'][0]);match.update(id='losers-test',round=-1,state='complete',winner='winner',p1='winner',scores='2 - 1',name1='Equipo Štørm · Androide 16 y Gokū '*8)
        snapshot['matches'].append(match)
        original=copy.deepcopy(snapshot)
        self.view.render(snapshot);self.view.show('losers')
        self.assertFalse(self.view.canvas.find_withtag('match:'+snapshot['matches'][0]['id']))
        self.view.choose(match['id']);self.view.resize(.15)
        items=self.view.canvas.find_withtag('match:'+match['id'])
        self.assertTrue(any(self.view.canvas.type(item)=='text' and self.view.canvas.itemcget(item,'fill')==ORANGE for item in items))
        self.assertIn(match['name1'],self.view.detail.get())
        self.assertIn('2 - 1',self.view.detail.get())
        self.assertEqual(snapshot,original)
        self.view.show('players')
        self.assertTrue(self.view.players.winfo_manager())

    def test_switch_to_single_elimination_resets_losers(self):
        snapshot=copy.deepcopy(self.snapshot)
        match=copy.deepcopy(snapshot['matches'][0]);match.update(id='negative',round=-1)
        snapshot['matches'].append(match)
        self.view.render(snapshot);self.view.show('losers');self.view.render(self.snapshot)
        self.assertEqual(self.view.tab,'main')
        self.view.render(None)
        self.assertEqual(self.view.visible_match_ids,[])

    def test_toolbar_wraps_without_clipping(self):
        self.root.attributes('-alpha',0);self.root.deiconify()
        self.view.pack_configure(fill='both',expand=True)
        self.view.render(self.snapshot)
        for width,row in ((520,1),(980,0)):
            self.root.geometry(f'{width}x600');self.root.update()
            self.assertEqual(int(self.view.zoom_area.grid_info()['row']),row)
            for b in self.view.tabs.values():
                self.assertLessEqual(b.winfo_x()+b.winfo_width(),b.master.winfo_width()+2)

    def test_every_match_reachable_without_scrolling(self):
        for width,height in ((520,430),(980,650),(1600,900)):
            self.root.geometry(f'{width}x{height}');self.root.update()
            self.view.show('main');self.view.render(self.snapshot);self.root.update()
            seen=set()
            for round_page in range(self.view.round_pages):
                self.view.round_page=round_page;self.view.match_page=0;self.view.render(self.snapshot)
                for match_page in range(self.view.match_pages):
                    self.view.match_page=match_page;self.view.render(self.snapshot)
                    seen.update(self.view.visible_match_ids)
                    for item in self.view.canvas.find_all():
                        if self.view.canvas.type(item)=='rectangle':
                            x,y,right,bottom=self.view.canvas.coords(item)
                            self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                            self.assertLessEqual(right,self.view.canvas.winfo_width())
                            self.assertLessEqual(bottom,self.view.canvas.winfo_height())
            self.assertEqual(seen,{m['id'] for m in self.snapshot['matches']})
            self.assertEqual(self.view.canvas.yview(),(0.,1.))
            self.assertEqual(self.view.canvas.xview(),(0.,1.))


if __name__=='__main__':unittest.main()
