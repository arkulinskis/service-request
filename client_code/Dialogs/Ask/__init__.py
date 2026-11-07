from anvil import *

from ._anvil_designer import AskTemplate
from ... import sr, state


class Ask(AskTemplate):
    """A short question before an action: cancel / back out / dispute (a reason), raise the bounty (two amounts),
    reject (admin). run(values) makes the server call; an expected problem stays in the dialog. Closes with True
    when done, None on Back.

        text_field = {"label", "min", "max", "placeholder", "value", "optional"}   (min 0 = not required)
        numbers = [{"label", "min", "max", "value"}, {...}]"""

    def __init__(self, title="", text="", ok="OK", danger=False, run=None, text_field=None, numbers=None, **properties):
        super().__init__(**properties)
        self._run = run
        self._text = text_field
        self._nums = numbers or []
        self.title_label.text = title
        state.heading(self.title_label, 2)
        self.text_label.text = text
        self.text_label.visible = bool(text)
        self.ok_button.text = ok
        self.ok_button.role = ["btn", "btn-danger", "btn-solid"] if danger else ["btn", "btn-primary"]
        self.numbers.visible = bool(self._nums)
        for spec, box, cap in zip(self._nums, [self.num1_box, self.num2_box], [self.dom_nodes["num1_cap"], self.dom_nodes["num2_cap"]]):
            cap.textContent = spec["label"]
            box.text = spec.get("value")
            state.set_control_attr(box, "min", spec.get("min"))
            state.set_control_attr(box, "max", spec.get("max"))
            state.set_control_attr(box, "step", 1)
        self.text_field.visible = bool(text_field)
        if text_field:
            cap = text_field["label"]
            self.dom_nodes["text_cap"].innerHTML = sr.esc(cap) + (" <em>(optional)</em>" if text_field.get("optional") else "")
            self.text_box.text = text_field.get("value") or ""
            self.text_box.placeholder = text_field.get("placeholder") or ""
            state.set_control_attr(self.text_box, "maxlength", text_field.get("max") or 800)

    @handle("back_button", "click")
    def back_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        values = {}
        for i, (spec, box) in enumerate(zip(self._nums, [self.num1_box, self.num2_box])):
            v = box.text
            if v in (None, ""):
                return self._fail("Fill in %s." % spec["label"].lower())
            v = float(v)
            if spec.get("min") is not None and v < spec["min"]:
                return self._fail("%s can't be less than %s." % (spec["label"], spec["min"]))
            if spec.get("max") is not None and v > spec["max"]:
                return self._fail("%s can't be more than %s." % (spec["label"], spec["max"]))
            values["n%d" % (i + 1)] = int(v) if v == int(v) else v
        if self._text:
            t = (self.text_box.text or "").strip()
            need = self._text.get("min") or 0
            if need and len(t) < need:
                return self._fail("Please write at least %d characters." % need)
            values["text"] = t
        self.error_label.visible = False
        self.ok_button.enabled = False
        try:
            r = self._run(values) if self._run else True
        finally:
            self.ok_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            return self._fail(r.get("error") or "That didn't work.")
        self.raise_event("x-close-alert", value=True)

    def _fail(self, message):
        self.error_label.text = message
        self.error_label.visible = True
