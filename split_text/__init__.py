from .split_text import split_text
# And add the extension to Krita's list of extensions:
Krita.instance().addExtension(split_text(Krita.instance()))