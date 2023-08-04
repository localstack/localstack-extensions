#!/usr/bin/env python

import configparser
import glob
import os


def main():
    root_path = os.path.join(os.path.dirname(__file__), '..')

    distributions = []
    for match in glob.glob("**/setup.cfg", root_dir=root_path):
        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(root_path, match))

        distributions.append(cfg['metadata'])

    print("| Extension | Install name | Version | Support status |")
    print("| --------- | ------------ | ------- | -------------- |")

    for metadata in sorted(distributions, key=lambda k: k['name']):
        display_name = metadata['summary'].removeprefix("LocalStack Extension: ")
        print(f"| [{display_name}]({metadata['url']}) | {metadata['name']} | {metadata['version']} | ? |")


if __name__ == "__main__":
    main()
