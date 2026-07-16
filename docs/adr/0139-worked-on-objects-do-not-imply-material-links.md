# Worked-On Objects Do Not Imply Material Links

A GPT-5.5 free-form Service candidate links a Material only when the source establishes that the material was supplied, purchased, or otherwise included in the same commercial fact. A noun naming the object of completed work does not by itself create a Material link: `Installed 10 steel doors using our crew` is Service-only with proposed Service `Steel door installation`, while `Supplied and installed 10 steel doors` is Bundled with one grounded Material and one grounded Service. This prevents service descriptions from inventing purchased Materials and preserves ADR 0114's requirement that both sides of a bundle be source-backed.

The model may use the worked-on object to normalize the Service name and must retain its exact Observed Name Text, but neither Project Memory nor semantic normalization may promote that object into a separate Material concept without supply or purchase evidence.
