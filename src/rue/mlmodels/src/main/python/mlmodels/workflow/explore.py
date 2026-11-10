import matplotlib.pyplot as plt


def explore_plot(label, data_pl, data_x, data_y, type="-", overlay=False, title=None):
    if not overlay:
        plt.figure(figsize=(16, 8))
    plt.plot(data_pl.select(data_x), data_pl.select(data_y), type, label=label)
    plt.xlabel(data_x)
    plt.ylabel(data_y)
    if title is not None:
        plt.title(title)
    plt.legend(loc="upper right")
