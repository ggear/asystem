import matplotlib.pyplot as plt


def show_plot(label, data_pl, data_x, data_y, type="-"):
    plt.rcParams["figure.figsize"] = (16, 8)
    plt.plot(data_pl.select(data_x), data_pl.select(data_y), type, label=label)
    plt.xlabel(data_x)
    plt.ylabel(data_y)
    plt.legend(loc="upper right")
