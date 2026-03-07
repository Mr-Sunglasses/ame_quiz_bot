from src.parser.quiz_parser import parse_single_block, parse_bulk


def test_parse_channel_tag_format():
    block = (
        "@aiapgetmadeeasy\n"
        "Q. अलङ्कृता रूपवती सुभगा कामरूपिणी is  ---\n"
        "as per सुश्रुत\n"
        "\n"
        "(A) रेवती\n"
        "(B) शकुनि\n"
        "(C) मुखमण्डिका\n"
        "(D) पूतना\n"
        "\n"
        "Ans - C\n"
        "\n"
        "Reference - su.ut.35\n"
    )
    pq, err = parse_single_block(block)
    assert err is None, f"Unexpected error: {err}"
    assert pq is not None
    assert pq.correct_index == 2  # C → index 2
    assert pq.reference == "su.ut.35"
    assert len(pq.options) == 4
    assert "सुश्रुत" in pq.text  # multi-line question text is joined


def test_parse_single_format_variant_a():
    block = (
        "Q- Fill the blank -रौधिरस्य तु गुल्मस्य गर्भकालव्यतिक्रमे । स्निग्धस्विन्नशरीरायै दद्यात.........(च)\n"
        "(A) स्नेह स्वेदनं\n"
        "(B) स्नेह बस्ती\n"
        "(C)  स्नेह वमनं\n"
        "(D) None of the above\n"
        "Ans- D\n"
        "Ref- स्नेह विरेचनं\n"
    )
    pq, err = parse_single_block(block)
    assert err is None
    assert pq is not None
    assert pq.correct_index == 3
    assert pq.reference is not None
    assert len(pq.options) == 4


def test_parse_single_format_variant_b():
    block = (
        "Q1. The blood supply of the SA node is most commonly from which artery?\n"
        "a) Left circumflex artery\n"
        "b) Right coronary artery\n"
        "c) Left anterior descending artery\n"
        "d) Posterior descending artery\n"
        "Ans: b) Right coronary artery\n"
        "Ref: ~60% cases RCA; ~40% LCX. (Gray’s Anatomy)\n"
    )
    pq, err = parse_single_block(block)
    assert err is None
    assert pq is not None
    assert pq.correct_index == 1
    assert pq.options[pq.correct_index].lower().startswith("right coronary")


def test_parse_bulk_example():
    content = (
        "Q1. Example 1?\n"
        "a) A\n"
        "b) B\n"
        "c) C\n"
        "d) D\n"
        "Ans: b) B\n"
        "\n"
        "Q2) Example 2?\n"
        "A) Alpha\n"
        "B) Beta\n"
        "C) Gamma\n"
        "D) Delta\n"
        "Answer: A\n"
        "---\n"
        "Q- Example 3 text\n"
        "1) One\n"
        "2) Two\n"
        "3) Three\n"
        "Ans- 2\n"
    )
    parsed, errors = parse_bulk(content)
    assert len(parsed) == 3
    assert len(errors) == 0
    assert parsed[0].correct_index == 1
    assert parsed[1].correct_index == 0
    assert parsed[2].correct_index == 1
