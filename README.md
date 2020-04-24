# shournal-to-snakemake

Transform a command series observed by 
[shournal](https://github.com/tycho-kirchner/shournal)
 to 
[snakemake](https://github.com/snakemake/snakemake)
 rules.

[shournal](https://github.com/tycho-kirchner/shournal) 
tracks read and written files of shell commands. Thus, for
each command the input- and output-section of a snakemake rule 
may be generated. Matched file-paths are automatically replaced
in the command string with {input} and {output}.


## Basic Usage
After 
[shournal](https://github.com/tycho-kirchner/shournal)
is installed, start a new (by shournal observed) shell session. Within that
perform the (shell-based) data analysis of your choice. 

Once done, from within the same shell-session, generate the snakemake rules by

```
shournal -q --output-format json -sid $SHOURNAL_SESSION_ID | shournal-to-snakemake
```

## Toy example
```
$ SHOURNAL_ENABLE
$ echo stuff > foo
$ cat foo > bar
$ shournal -q --output-format json -sid $SHOURNAL_SESSION_ID | shournal-to-snakemake
rule undefined_1:
    output:
        "foo",
    shell:
        # raw: echo stuff > foo
        "echo stuff > {output}"


rule undefined_2:
    input:
        "foo",
    output:
        "bar",
    shell:
        # raw: cat foo > bar
        "cat {input} > {output}"
```

## General hints
* Don't change the working directory during the workflow.
* Do not use wildcards or variables (in file-paths), otherwise the files
  in the command string cannot be correctly replaced by {input} or {output}.
* Stick to basic posix shell syntax
  

## Installation

### PyPi
Install from PyPi by executing the following command in a terminal:
```
pip install shournal-to-snakemake
```

### From Source
Create a wheel directly from source by executing
```
python3 setup.py sdist bdist_wheel
```
Install the wheel as usual, e.g. by
```
pip3 install --user dist/shournal_to_snakemake-VERSION-*.whl
```


## License

Copyright &copy; 2020 Tycho Kirchner (see LICENSE)


