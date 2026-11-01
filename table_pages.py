"""Bounded table pages; keep all rows reachable without a scrollbar."""
import tkinter as tk
from tkinter import ttk
from battle_hub import PANEL,MUTED,button


class TablePages:
    def __init__(self,tree):
        self.tree=tree;self.rows=[];self.page=0;self.capacity=1;self.busy=False
        self.bar=tk.Frame(tree.master,bg=tree.master.cget('bg'))
        self.previous=button(self.bar,'‹',lambda:self.move(-1));self.previous.configure(padx=10,pady=2)
        self.previous.pack(side='left')
        self.text=tk.Label(self.bar,bg=self.bar.cget('bg'),fg=MUTED,font=('Segoe UI',9));self.text.pack(side='left',expand=True)
        self.next=button(self.bar,'›',lambda:self.move(1));self.next.configure(padx=10,pady=2);self.next.pack(side='right')
        self.bar.pack(fill='x',padx=18,pady=(2,6))
        tree.configure(height=1)
        tree.bind('<Configure>',lambda e:self.render(),add='+')
        tree.bind('<MouseWheel>',lambda e:'break')
        self.render()

    def reset(self):
        for row in self.rows:
            if self.tree.exists(row):self.tree.move(row,'','end')
        self.rows=[]

    def capture(self):
        self.rows=list(self.tree.get_children());self.render()

    def move(self,delta):
        self.tree.selection_remove(self.tree.selection())
        self.page=max(0,min(self.pages()-1,self.page+delta));self.render()

    def pages(self):return max(1,(len(self.rows)+self.capacity-1)//self.capacity)

    def render(self):
        if self.busy or not self.tree.winfo_exists():return
        self.busy=True
        try:
            style=ttk.Style(self.tree)
            row_height=int(style.lookup(self.tree.cget('style'),'rowheight') or 32)
            heading=28 if 'headings' in str(self.tree.cget('show')) else 0
            self.capacity=max(1,(self.tree.winfo_height()-heading-4)//row_height)
            self.page=min(self.page,self.pages()-1)
            for row in self.rows:
                if self.tree.exists(row):self.tree.detach(row)
            start=self.page*self.capacity
            for row in self.rows[start:start+self.capacity]:
                if self.tree.exists(row):self.tree.move(row,'','end')
            visible=set(self.tree.get_children())
            for row in self.tree.selection():
                if row not in visible:self.tree.selection_remove(row)
            self.text.configure(text=f'{start+1}–{min(start+self.capacity,len(self.rows))} / {len(self.rows)}' if self.rows else 'Sin elementos')
            self.previous.configure(state='normal' if self.page else 'disabled')
            self.next.configure(state='normal' if self.page+1<self.pages() else 'disabled')
        finally:self.busy=False
