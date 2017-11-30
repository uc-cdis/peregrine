from gdcapi.errors import UserError
from flask import jsonify

PROJECT_PHSID_MAPPING = {
    'phs000178': {
        'TCGA-LAML', 'TCGA-ACC', 'TCGA-BLCA', 'TCGA-LGG', 'TCGA-BRCA', 'TCGA-CESC', 'TCGA-CHOL', 'TCGA-COAD', 'TCGA-ESCA',
        'TCGA-GBM', 'TCGA-HNSC', 'TCGA-KICH', 'TCGA-KIRC', 'TCGA-KIRP', 'TCGA-LIHC', 'TCGA-LUAD', 'TCGA-LUSC', 'TCGA-DLBC',
        'TCGA-MESO', 'TCGA-OV', 'TCGA-PAAD', 'TCGA-PCPG', 'TCGA-PRAD', 'TCGA-READ', 'TCGA-SARC', 'TCGA-SKCM', 'TCGA-STAD',
        'TCGA-TGCT', 'TCGA-THYM', 'TCGA-THCA', 'TCGA-UCS', 'TCGA-UCEC', 'TCGA-UVM', 'TCGA-MISC', 'TCGA-LCML', 'TCGA-FPPP',
        'TCGA-CNTL'},
    'phs000218': {
        'TARGET-ALL-P1', 'TARGET-ALL-P2', 'TARGET-AML', 'TARGET-AML-IF', 'TARGET-WT', 'TARGET-CCSK', 'TARGET-RT', 'TARGET-NBL', 'TARGET-OS',
        'MDLS'},
    'phs000463': {'TARGET-ALL-P1'},
    'phs000464': {'TARGET-ALL-P2'},
    'phs000465': {'TARGET-AML'},
    'phs000515': {'TARGET-AML-IF'},
    'phs000471': {'TARGET-WT'},
    'phs000466': {'TARGET-CCSK'},
    'phs000470': {'TARGET-RT'},
    'phs000467': {'TARGET-NBL'},
    'phs000468': {'TARGET-OS'},
    'phs000469': {'MDLS'}
}


def get_user_projects(ids):
    """Takes a list of strings specifying the phsid assigned to a
    user by dbGaP and returns a list of projects that user is a part of.

    :param ids:
        Should be a list of phsid strings that the user belongs to.

    :returns:
        list of project codes the user has access to.

    """

    if ids is None:
        raise UserError(
            'Invalid query params. Please specify ids [ids=id1,id2].')

    projects = set()
    try:
        for phsid in ids:
            if phsid in PROJECT_PHSID_MAPPING:
                projects |= PROJECT_PHSID_MAPPING[phsid]

    except Exception, msg:
        raise UserError(
            'Invalid query params. Poorly formated id list [ids=id1,id2].')
    else:
        return list(projects)
