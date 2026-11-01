"""Responsive layout primitives shared by the desktop menus."""


def action_grid(parent, widgets, minimum=190):
    """Wrap actions together, with equal widths and no clipped packed buttons."""
    for widget in widgets:
        widget.pack_forget();widget.grid_forget()
    state=[None]
    def arrange(event=None):
        columns=max(1,min(len(widgets),parent.winfo_width()//minimum))
        if columns==state[0]:return
        state[0]=columns
        for col in range(len(widgets)):parent.columnconfigure(col,weight=1 if col<columns else 0,uniform='actions' if col<columns else '')
        for index,widget in enumerate(widgets):
            widget.grid(row=index//columns,column=index%columns,sticky='ew',padx=4,pady=4)
    pending=[None]
    def initial_layout():
        pending[0]=None;arrange()
    def cancel_initial(event):
        if event.widget is parent and pending[0]:
            parent.after_cancel(pending[0]);pending[0]=None
    parent.bind('<Configure>',arrange,add='+')
    parent.bind('<Destroy>',cancel_initial,add='+')
    pending[0]=parent.after_idle(initial_layout)


def fit_columns(tree, proportions):
    """Keep visible table columns inside the available width."""
    def arrange(event):
        width=max(1,event.width-8);total=sum(proportions.values())
        for key,weight in proportions.items():
            tree.column(key,width=max(30,int(width*weight/total)),minwidth=30,stretch=True)
    tree.bind('<Configure>',arrange,add='+')
