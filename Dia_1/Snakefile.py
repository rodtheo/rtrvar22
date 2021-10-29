import pandas as pd

configfile: "config.yaml"

samples = pd.read_table(config["samples"])
#.set_index("sample", drop=False)

# def get_genome_prefix(wildcards):
#         gen = config["genome"]
#         return gen[:-]

SAMPLE = ["amostra-lbb"]

rule all:
    input:
        expand("{sample}.vcf.gz", sample=SAMPLE)
        # expand("{sample}.txt", sample=SAMPLE)


rule unpack_gz:
    input:
        expand("{genome}.gz", genome=config["genome"])
    output:
        expand("{genome}", genome=config["genome"])
    shell:
        "zcat {input} > {output}"

rule mapping_reads:
    input:
        fq1="{sample}_R1.fq.gz",
        fq2="{sample}_R2.fq.gz",
        genome=config["genome"]
    output:
        temp("{sample}.sam")
    threads:
        4
    shell:
        '''
        bwa index {input.genome} &&
            bwa mem -t {threads} {input.genome} {input.fq1} {input.fq2} > {output}
        '''

rule convert_to_bam:
    input:
        "{sample}.sam"
    output:
        temp("{sample}.bam")
    shell:
        "sambamba view --format=bam --sam-input --output-filename {output} {input}"

rule sort_bam:
    input:
        "{sample}.bam"
    output:
        temp("{sample}.sorted.bam")
    shell:
        "sambamba sort -o {output} {input}"

# rule index_fasta:
#     input:
#         config["genome"]
#     output:
#         expand("{genome}.fai", genome=config["genome"])
#     shell:
#         "seqkit faidx --out-file {output} {input}"

rule dict_fasta_gatk:
    input:
        gen=config["genome"]
    output:
        expand("{genome}.fai", genome=config["genome"])
    shell:
        'seqkit faidx {input.gen} && docker run --user "$(id -u):$(id -g)" -v $PWD:/home/Dia_1 -w /home/Dia_1 --rm broadinstitute/gatk:4.2.2.0 gatk CreateSequenceDictionary -R {input.gen}'


rule markduplicates_bam:
    input:
        samp="{sample}.sorted.bam",
        genome=config["genome"]
    output:
        temp("{sample}.sorted.mdup.bam")
    shell:
        'docker run --user "$(id -u):$(id -g)" -v $PWD:/home/Dia_1 -w /home/Dia_1 --rm -it broadinstitute/gatk:4.2.2.0 gatk MarkDuplicates -R {input.genome} -I {input.samp} -O {output} --METRICS_FILE metrics_gatk_markduplicates.txt'

rule add_RG_in_bam:
    input:
        "{sample}.sorted.bam"
    output:
        temp("{sample}.sorted.mdup.addRG.bam")
    shell:
        'docker run --user "$(id -u):$(id -g)" -v $PWD:/home/Dia_1 -w /home/Dia_1 --rm  broadinstitute/gatk:4.2.2.0 gatk AddOrReplaceReadGroups --INPUT {input} --OUTPUT {output} --RGLB lib1 --RGPL ILLUMINA --RGPU unit1 --RGSM mend'

rule index_feature_gatk:
    input:
        known_vcf=config["known_vcf"]
    output:
        expand("{known_vcf}.idx", known_vcf=config["known_vcf"])
    shell:
        'docker run --user "$(id -u):$(id -g)" -v $PWD:/home/Dia_1 --rm -w /home/Dia_1  broadinstitute/gatk:4.2.2.0 gatk IndexFeatureFile -I {input.known_vcf} -O {output}'

rule base_recalibration_gatk:
    input:
        known_vcf_idx=expand("{kv}.idx", kv=config["known_vcf"]),
        known_vcf=config["known_vcf"],
        genome=config["genome"],
        bam=expand("{sample}.sorted.mdup.addRG.bam", sample=SAMPLE)
    output:
        "recal_data.table"
    shell:
        'docker run --user "$(id -u):$(id -g)" -v $PWD:/home/Dia_1 --rm -w /home/Dia_1  broadinstitute/gatk:4.2.2.0 gatk BaseRecalibrator -R {input.genome} -I {input.bam} --known-sites {input.known_vcf} -O {output}'

rule apply_base_recalibration:
    input:
        genome=config["genome"],
        bam="{sample}.sorted.mdup.addRG.bam",
        dt="recal_data.table"
    output:
        "{sample}.sorted.mdup.addRG.recal.bam"
    shell:
        'docker run --user "$(id -u):$(id -g)" -v $PWD:/home/Dia_1 --rm -w /home/Dia_1 broadinstitute/gatk:4.2.2.0 gatk ApplyBQSR -R {input.genome} -I {input.bam} -bqsr {input.dt} -O {output}'

rule call_vars:
    input:
        genome=config["genome"],
        bam="{sample}.sorted.mdup.addRG.recal.bam",
        dict=expand("{genome}.fai", genome=config["genome"])
    output:
        vcf="{sample}.vcf.gz",
        bamout="{sample}.sorted.mdup.addRG.recal.bamout.bam"
    shell:
        'docker run --user "$(id -u):$(id -g)" -v $PWD:/home/Dia_1 --rm -w /home/Dia_1 broadinstitute/gatk:4.2.2.0 gatk HaplotypeCaller -R {input.genome} -I {input.bam} -O {output.vcf} -bamout {output.bamout}'


#
# rule sort:
#     input:
#         "{sample}_R1.fq.gz",
#         "{sample}_R2.fq.gz",
#         "{sample}.sam",
#         "ok_dict.txt",
#         genome=config["genome"]
#     output:
#         "{sample}.txt"
#     shell:
#         "echo OK >> {output}"

# rule mapping_reads:
#     input:
#         fq1="{sample}_R1.fq.gz",
#         fq2="{sample}_R2.fq.gz",
#         genome=config["genome"]
#     output:
