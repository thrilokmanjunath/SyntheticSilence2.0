"""
References in TACL author-year style, checked against primary sources (see FORMAT_NOTES.md).

CITES      key -> (text used in running text, year)
REFERENCES key -> {"sort": sort key, "short": natbib short label, "long": natbib long author list,
                   "text": reference-list entry; <i>..</i> marks italics}
"""

CITES = {
    "ji2023": ("Ji et al.", "2023"),
    "lin2022": ("Lin et al.", "2022"),
    "guo2022": ("Guo et al.", "2022"),
    "thorne2018": ("Thorne et al.", "2018"),
    "ss2026": ("Anonymous", "2026"),
    "schlichtkrull2023": ("Schlichtkrull et al.", "2023"),
    "manakul2023": ("Manakul et al.", "2023"),
    "min2023": ("Min et al.", "2023"),
    "mahalanobis1936": ("Mahalanobis", "1936"),
    "ledoit2004": ("Ledoit and Wolf", "2004"),
    "reimers2019": ("Reimers and Gurevych", "2019"),
    "wang2020": ("Wang et al.", "2020"),
    "angelopoulos2021": ("Angelopoulos and Bates", "2023"),
    "zheng2023": ("Zheng et al.", "2023"),
    "priem2022": ("Priem et al.", "2022"),
    "wilson1927": ("Wilson", "1927"),
    "efron1979": ("Efron", "1979"),
    "cover2006": ("Cover and Thomas", "2006"),
    "horn2013": ("Horn and Johnson", "2013"),
}

_ACL = "Association for Computational Linguistics"

REFERENCES = {
    "ji2023": {"sort": "ji2023", "text":
        "Ziwei Ji, Nayeon Lee, Rita Frieske, Tiezheng Yu, Dan Su, Yan Xu, Etsuko Ishii, Ye Jin Bang, "
        "Andrea Madotto, and Pascale Fung. 2023. Survey of hallucination in natural language generation. "
        "<i>ACM Computing Surveys</i>, 55(12):248:1–248:38. https://doi.org/10.1145/3571730"},
    "lin2022": {"sort": "lin2022", "text":
        "Stephanie Lin, Jacob Hilton, and Owain Evans. 2022. TruthfulQA: Measuring how models mimic human "
        "falsehoods. In <i>Proceedings of the 60th Annual Meeting of the Association for Computational "
        "Linguistics (Volume 1: Long Papers)</i>, pages 3214–3252, Dublin, Ireland. " + _ACL + ". "
        "https://doi.org/10.18653/v1/2022.acl-long.229"},
    "guo2022": {"sort": "guo2022", "text":
        "Zhijiang Guo, Michael Schlichtkrull, and Andreas Vlachos. 2022. A survey on automated "
        "fact-checking. <i>Transactions of the Association for Computational Linguistics</i>, 10:178–206. "
        "https://doi.org/10.1162/tacl_a_00454"},
    "thorne2018": {"sort": "thorne2018", "text":
        "James Thorne, Andreas Vlachos, Christos Christodoulopoulos, and Arpit Mittal. 2018. FEVER: A "
        "large-scale dataset for fact extraction and VERification. In <i>Proceedings of the 2018 Conference "
        "of the North American Chapter of the Association for Computational Linguistics: Human Language "
        "Technologies, Volume 1 (Long Papers)</i>, pages 809–819, New Orleans, Louisiana. " + _ACL + ". "
        "https://doi.org/10.18653/v1/N18-1074"},
    "ss2026": {"sort": "anonymous2026", "text":
        "Anonymous. 2026. Synthetic Silence 2.0: Evaluating claim-space density for evidence insufficiency "
        "under construction and reference-manifold shift. Unpublished manuscript."},
    "schlichtkrull2023": {"sort": "schlichtkrull2023", "text":
        "Michael Schlichtkrull, Zhijiang Guo, and Andreas Vlachos. 2023. AVeriTeC: A dataset for real-world "
        "claim verification with evidence from the web. In <i>Advances in Neural Information Processing "
        "Systems</i>, volume 36, pages 65128–65167. Curran Associates, Inc."},
    "manakul2023": {"sort": "manakul2023", "text":
        "Potsawee Manakul, Adian Liusie, and Mark Gales. 2023. SelfCheckGPT: Zero-resource black-box "
        "hallucination detection for generative large language models. In <i>Proceedings of the 2023 "
        "Conference on Empirical Methods in Natural Language Processing</i>, pages 9004–9017, "
        "Singapore. " + _ACL + ". https://doi.org/10.18653/v1/2023.emnlp-main.557"},
    "min2023": {"sort": "min2023", "text":
        "Sewon Min, Kalpesh Krishna, Xinxi Lyu, Mike Lewis, Wen-tau Yih, Pang Wei Koh, Mohit Iyyer, Luke "
        "Zettlemoyer, and Hannaneh Hajishirzi. 2023. FActScore: Fine-grained atomic evaluation of factual "
        "precision in long form text generation. In <i>Proceedings of the 2023 Conference on Empirical "
        "Methods in Natural Language Processing</i>, pages 12076–12100, Singapore. " + _ACL + ". "
        "https://doi.org/10.18653/v1/2023.emnlp-main.741"},
    "mahalanobis1936": {"sort": "mahalanobis1936", "text":
        "Prasanta Chandra Mahalanobis. 1936. On the generalized distance in statistics. <i>Proceedings of "
        "the National Institute of Sciences of India</i>, 2(1):49–55."},
    "ledoit2004": {"sort": "ledoit2004", "text":
        "Olivier Ledoit and Michael Wolf. 2004. A well-conditioned estimator for large-dimensional "
        "covariance matrices. <i>Journal of Multivariate Analysis</i>, 88(2):365–411. "
        "https://doi.org/10.1016/S0047-259X(03)00096-4"},
    "reimers2019": {"sort": "reimers2019", "text":
        "Nils Reimers and Iryna Gurevych. 2019. Sentence-BERT: Sentence embeddings using Siamese "
        "BERT-networks. In <i>Proceedings of the 2019 Conference on Empirical Methods in Natural Language "
        "Processing and the 9th International Joint Conference on Natural Language Processing "
        "(EMNLP-IJCNLP)</i>, pages 3982–3992, Hong Kong, China. " + _ACL + ". "
        "https://doi.org/10.18653/v1/D19-1410"},
    "wang2020": {"sort": "wang2020", "text":
        "Wenhui Wang, Furu Wei, Li Dong, Hangbo Bao, Nan Yang, and Ming Zhou. 2020. MiniLM: Deep "
        "self-attention distillation for task-agnostic compression of pre-trained transformers. In "
        "<i>Advances in Neural Information Processing Systems</i>, volume 33, pages 5776–5788. Curran "
        "Associates, Inc."},
    "angelopoulos2021": {"sort": "angelopoulos2023", "text":
        "Anastasios N. Angelopoulos and Stephen Bates. 2023. Conformal prediction: A gentle introduction. "
        "<i>Foundations and Trends in Machine Learning</i>, 16(4):494–591. "
        "https://doi.org/10.1561/2200000101"},
    "zheng2023": {"sort": "zheng2023", "text":
        "Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, "
        "Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, and Ion Stoica. 2023. Judging "
        "LLM-as-a-judge with MT-Bench and Chatbot Arena. In <i>Advances in Neural Information Processing "
        "Systems</i>, volume 36, pages 46595–46623. Curran Associates, Inc."},
    "priem2022": {"sort": "priem2022", "text":
        "Jason Priem, Heather Piwowar, and Richard Orr. 2022. OpenAlex: A fully-open index of scholarly "
        "works, authors, venues, institutions, and concepts. <i>arXiv preprint arXiv:2205.01833</i>."},
    "wilson1927": {"sort": "wilson1927", "text":
        "Edwin B. Wilson. 1927. Probable inference, the law of succession, and statistical inference. "
        "<i>Journal of the American Statistical Association</i>, 22(158):209–212. "
        "https://doi.org/10.1080/01621459.1927.10502953"},
    "efron1979": {"sort": "efron1979", "text":
        "Bradley Efron. 1979. Bootstrap methods: Another look at the jackknife. <i>The Annals of "
        "Statistics</i>, 7(1):1–26. https://doi.org/10.1214/aos/1176344552"},
    "cover2006": {"sort": "cover2006", "text":
        "Thomas M. Cover and Joy A. Thomas. 2006. <i>Elements of Information Theory</i>, second edition. "
        "Wiley-Interscience, Hoboken, NJ."},
    "horn2013": {"sort": "horn2013", "text":
        "Roger A. Horn and Charles R. Johnson. 2013. <i>Matrix Analysis</i>, second edition. Cambridge "
        "University Press, Cambridge, UK."},
}

# natbib long author lists for \bibitem[Short(Year)Long]{key}
LONG_AUTHORS = {
    "ji2023": "Ji, Lee, Frieske, Yu, Su, Xu, Ishii, Bang, Madotto, and Fung",
    "lin2022": "Lin, Hilton, and Evans",
    "guo2022": "Guo, Schlichtkrull, and Vlachos",
    "thorne2018": "Thorne, Vlachos, Christodoulopoulos, and Mittal",
    "ss2026": "Anonymous",
    "schlichtkrull2023": "Schlichtkrull, Guo, and Vlachos",
    "manakul2023": "Manakul, Liusie, and Gales",
    "min2023": "Min, Krishna, Lyu, Lewis, Yih, Koh, Iyyer, Zettlemoyer, and Hajishirzi",
    "mahalanobis1936": "Mahalanobis",
    "ledoit2004": "Ledoit and Wolf",
    "reimers2019": "Reimers and Gurevych",
    "wang2020": "Wang, Wei, Dong, Bao, Yang, and Zhou",
    "angelopoulos2021": "Angelopoulos and Bates",
    "zheng2023": "Zheng, Chiang, Sheng, Zhuang, Wu, Zhuang, Lin, Li, Li, Xing, Zhang, Gonzalez, and Stoica",
    "priem2022": "Priem, Piwowar, and Orr",
    "wilson1927": "Wilson",
    "efron1979": "Efron",
    "cover2006": "Cover and Thomas",
    "horn2013": "Horn and Johnson",
}
