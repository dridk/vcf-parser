# Standard imports
import vcf

# Custom imports
from abstractreader import AbstractReader, sanitize_field_name
from annotationparser import VepParser, SnpEffParser

import logging


#  Fixing PyVCF bug
#  https://github.com/jamescasbon/PyVCF/pull/320
def _map(self, func, iterable, bad=[".", "", "NA"]):
    """``map``, but make bad values None."""
    return [func(x) if x not in bad else None for x in iterable]


vcf.Reader._map = _map

#  End fixing


LOGGER = logging.getLogger("parser")

VCF_TYPE_MAPPING = {
    "Float": "float",
    "Integer": "int",
    "Flag": "bool",
    "String": "str",
    "Character": "str",
}


class VcfReader(AbstractReader):
    """VCF parser to extract data from vcf file

    .. seealso:: AbstractReader class for more information.

    Attributes:
        annotation_parser (object): Support "VepParser()" and "SnpeffParser()"
    """

    def __init__(self, device, annotation_parser: str = None):
        """Construct a VCF Reader

        :param device: File device handler returned by open.
        :key annotation_parser (str): "vep" or "snpeff"
            This argument forces the reader to use a specific parser for
            the annotations. By default it's None: no parser will be used,
            annotations will not be taken into account.
        """
        super().__init__(device)

        vcf_reader = vcf.VCFReader(device)
        self.samples = vcf_reader.samples
        self.annotation_parser = None
        self.metadata = vcf_reader.metadata
        self._set_annotation_parser(annotation_parser)

    def get_fields(self):
        """Get full fields descriptions

        This function is called a first time before variants insertion.

        .. note:: Annotations fields are added here if they exist in the file.

        .. seealso:: parse_fields()

        :return: Tuple of fields.
            Each field is a dict with the following keys:
                name, category, description, type
            Some fields have an additional constraint key when they are destined
            to be a primary key in the database.
            Annotations fields are added here if they exist in the file.
            .. seealso parse_fields() for basic default fields.
        :rtype: <tuple <dict>>
        """
        if not hasattr(self, "fields"):

            # Sanitize fields names
            # PS: annotations fields names are sanitized by the annotation_parser
            fields = tuple(self.parse_fields())
            for field in fields:
                field["name"] = sanitize_field_name(field["name"])

            if self.annotation_parser:
                # If "ANN" is a field in the current VCF:
                # Remove and parse special annotations
                self.fields = tuple(self.annotation_parser.parse_fields(fields))
            else:
                self.fields = fields
        return self.fields

    def get_variants(self):
        """Get variants as an iterable of dictionnaries

        "annotations" key is added here with the list of annotations if
        they exist in the file.

        .. seealso:: parse_variant()

        :return: Generator of full variants with "annotations" key.
        :rtype: <generator <dict>>
        """

        if not hasattr(self, "fields"):
            # This is a bad caching code ....
            self.get_fields()

        if self.annotation_parser:
            yield from self.annotation_parser.parse_variants(self.parse_variants())
        else:
            yield from self.parse_variants()

    def parse_variants(self):
        """Read file and parse variants

        .. note:: An estimation of the progression is made here by updating
            self.read_bytes attribute.

        :return: Generator of variants.
        :rtype: <generator <dict>>
        """
        # loop over record
        self.device.seek(0)
        vcf_reader = vcf.VCFReader(self.device)
        import sys

        # TODO : ugly for testing progression .. see #60
        self.read_bytes = self._init_read_bytes(vcf_reader)

        # Genotype format
        formats = [i for i in vcf_reader.formats]

        for record in vcf_reader:

            # elf.read_bytes += sys.getsizeof(record)
            self.read_bytes += self._get_record_size(record)

            # split row with multiple alt
            for index, alt in enumerate(record.ALT):
                # Remap some columns
                variant = {
                    "chr": record.CHROM,
                    "pos": record.POS,
                    "ref": record.REF,
                    "alt": str(alt),
                    "rsid": record.ID,  # Avoid id column duplication in DB
                    "qual": record.QUAL,
                    "filter": "" if record.FILTER is None else ",".join(record.FILTER),
                }

                forbidden_field = ("chr", "pos", "ref", "alt", "rsid", "qual", "filter")

                # Parse info
                for name in record.INFO:
                    if name.lower() not in forbidden_field:
                        if isinstance(record.INFO[name], list):
                            variant[name.lower()] = ",".join(
                                [str(i) for i in record.INFO[name]]
                            )
                        else:
                            variant[name.lower()] = record.INFO[name]

                # parse sample
                if record.samples:
                    variant["samples"] = []
                    for sample in record.samples:
                        sample_data = {}
                        sample_data["name"] = sample.sample

                        #  Load sample annotations
                        sample_ann = {}
                        for key in formats:
                            try:
                                value = sample[key]
                                if type(value) == list:
                                    value = ",".join([str(i) for i in value])
                                sample_ann[str.lower(key)] = value
                            except:
                                LOGGER.debug(
                                    f"VCFReader::parse: {key} not defined in genotype "
                                )

                        sample_data.update(sample_ann)

                        sample_data["gt"] = (
                            -1 if sample.gt_type == None else sample.gt_type
                        )
                        variant["samples"].append(sample_data)

                yield variant

                #     # #PARSE Annotation
                #     # if category == "annotation": #=== PARSE Special Annotation ===
                #     #     # each variant can have multiple annotation. Create then many variants
                #     #     variant["annotation"] = []
                #     #     annotations = record.INFO["ANN"]
                #     #     for annotation in annotations:
                #     #         variant["annotation"].append(
                #     #             self.parser.parse_variant(annotation)
                #     #         )

    def parse_fields(self):
        """Extract fields informations from VCF fields

        .. note:: Fields used in PRIMARY KEYS have the constraint NOT NULL.
            By default, all other fields can have NULL values.

        :return: Generator of fields.
            Each field is a dict with the following keys:
                name, category, description, type
            Some fields have an additional constraint key when they are destined
            to be a primary key in the database.
        :rtype: <generator <dict>>
        """
        yield {
            "name": "chr",
            "category": "variants",
            "description": "chromosom",
            "type": "str",
            "constraint": "NOT NULL",
        }
        yield {
            "name": "pos",
            "category": "variants",
            "description": "position",
            "type": "int",
            "constraint": "NOT NULL",
        }
        yield {
            "name": "ref",
            "category": "variants",
            "description": "reference base",
            "type": "str",
            "constraint": "NOT NULL",
        }
        yield {
            "name": "alt",
            "category": "variants",
            "description": "alternative base",
            "type": "str",
            "constraint": "NOT NULL",
        }
        yield {
            "name": "rsid",
            "category": "variants",
            "description": "rsid",
            "type": "str",
        }
        yield {
            "name": "qual",
            "category": "variants",
            "description": "quality",
            "type": "int",
        }
        yield {
            "name": "filter",
            "category": "variants",
            "description": "filter",
            "type": "str",
        }

        # Reads VCF INFO
        self.device.seek(0)
        vcf_reader = vcf.VCFReader(self.device)

        #  Reads VCF info
        for key, info in vcf_reader.infos.items():

            # if key == "ANN": # Parse special annotation
            #     yield from self.parser.parse_fields(info.desc)
            # else:

            yield {
                "name": key.lower(),
                "category": "variants",
                "description": info.desc,
                "type": VCF_TYPE_MAPPING[info.type],
            }

        # Reads VCF FORMAT
        for key, info in vcf_reader.formats.items():
            yield {
                "name": key.lower(),
                "category": "samples",
                "description": info.desc,
                "type": VCF_TYPE_MAPPING[info.type],
            }

    def get_samples(self):
        """Return list of samples."""
        return self.samples

    def _set_annotation_parser(self, parser: str):
        """Set the given annotation parser"""
        if parser == "vep":
            self.annotation_parser = VepParser()

        if parser == "snpeff":
            self.annotation_parser = SnpEffParser()

    def _get_record_size(self, rec):
        """Approximate record size in bytes"""
        # TODO : ugly .. For testing progression
        return (
            len(
                str(rec.CHROM)
                + str(rec.POS)
                + str(rec.ID)
                + str(rec.REF)
                + str(rec.ALT)
                + str(rec.QUAL)
                + str(rec.FILTER)
                + str(rec.INFO)
                + str(rec.FORMAT)
                + str(rec.samples)
            )
            - 10
        )

    def _init_read_bytes(self, reader):
        """Init read bytes : It's the size in bytes of header data file"""
        return 0

    def __repr__(self):
        return f"VCF Reader using {type(self.annotation_parser).__name__}"

    def get_metadatas(self):
        """override from AbstractReaer """
        output = {}
        output["filename"] = self.device.name

        for key, value in self.metadata.items():
            output[key] = str(value)

        return output
