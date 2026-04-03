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


def test_numbered_list_in_question_signs_of_death():
    block = (
        "Q. 29. Consider the following signs of death:\n"
        "1. Algor mortis (Cooling of the body)\n"
        "2. Livor mortis (Post-mortem staining)\n"
        "3. Rigor mortis (Stiffening of muscles)\n"
        "How many of the above are considered \"early\" signs of death?\n"
        "(A) Only one\n"
        "(B) Only two\n"
        "(C) All three\n"
        "(D) None\n"
        "Ans - C\n"
        "Reference - All three are considered early changes following death, occurring before the onset of putrefaction (which is a late sign). (Ref: Reddy's FMT)\n"
    )
    pq, err = parse_single_block(block)
    assert err is None, f"Unexpected error: {err}"
    assert pq is not None
    assert pq.correct_index == 2
    assert pq.options == ["Only one", "Only two", "All three", "None"]
    assert "Algor mortis" in pq.text
    assert "Livor mortis" in pq.text
    assert "Rigor mortis" in pq.text
    assert "How many of the above" in pq.text
    assert pq.reference is not None
    assert "Reddy" in pq.reference


def test_numbered_list_in_question_vaccines():
    block = (
        "Q. 2. Consider the following live attenuated vaccines:\n"
        "1. BCG\n"
        "2. Yellow Fever\n"
        "3. Salk Polio Vaccine\n"
        "4. Measles\n"
        "How many of the above are Live Attenuated Vaccines?\n"
        "(A) Only one\n"
        "(B) Only two\n"
        "(C) Only three\n"
        "(D) All four\n"
        "Ans - C\n"
        "Reference - Only three are correct (BCG, Yellow Fever, Measles). Salk is a killed (inactivated) polio vaccine, whereas Sabin (OPV) is live. (Ref: Park's Textbook of PSM)\n"
    )
    pq, err = parse_single_block(block)
    assert err is None, f"Unexpected error: {err}"
    assert pq is not None
    assert pq.correct_index == 2
    assert pq.options == ["Only one", "Only two", "Only three", "All four"]
    assert "BCG" in pq.text
    assert "Salk Polio Vaccine" in pq.text
    assert "How many of the above" in pq.text
    assert pq.reference is not None
    assert "Park" in pq.reference


def test_matching_question_with_pretext():
    block = (
        "Q. Match the following with respective संख्या\n"
        "\n"
        "1) प्राकृत वर्ण           a) 4 \n"
        "2) स्वप्न                    b) 7 \n"
        "3) छाया                   c) 5 \n"
        "4) प्रकृति                 d) 6\n"
        "\n"
        "(A) 1-a, 2-b, 3-c, 4-d\n"
        "(B) 1-c, 2-a, 3-b, 4-d\n"
        "(C) 1-a, 2-c, 3-b, 4-d\n"
        "(D) 1-c, 2-d, 3-b, 4-a\n"
        "\n"
        "Ans - A\n"
        "\n"
        "Ref -  Cha. Indriya\n"
    )
    pq, err = parse_single_block(block)
    assert err is None, f"Unexpected error: {err}"
    assert pq is not None
    assert pq.correct_index == 0
    assert pq.options == [
        "1-a, 2-b, 3-c, 4-d",
        "1-c, 2-a, 3-b, 4-d",
        "1-a, 2-c, 3-b, 4-d",
        "1-c, 2-d, 3-b, 4-a",
    ]
    assert "Match the following" in pq.text
    assert pq.pretext is not None
    assert "प्राकृत वर्ण" in pq.pretext
    assert "स्वप्न" in pq.pretext
    assert "छाया" in pq.pretext
    assert "प्रकृति" in pq.pretext
    assert pq.reference is not None
    assert "Cha. Indriya" in pq.reference


def test_non_matching_question_has_no_pretext():
    block = (
        "Q1. What is the capital of France?\n"
        "(A) London\n"
        "(B) Paris\n"
        "(C) Berlin\n"
        "(D) Madrid\n"
        "Ans - B\n"
    )
    pq, err = parse_single_block(block)
    assert err is None
    assert pq is not None
    assert pq.pretext is None
    assert pq.correct_index == 1


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


def test_parse_bulk_matching_question():
    content = (
        "Q. Match the following with respective संख्या\n"
        "\n"
        "1) प्राकृत वर्ण           a) 4 \n"
        "2) स्वप्न                    b) 7 \n"
        "3) छाया                   c) 5 \n"
        "4) प्रकृति                 d) 6\n"
        "\n"
        "(A) 1-a, 2-b, 3-c, 4-d\n"
        "(B) 1-c, 2-a, 3-b, 4-d\n"
        "(C) 1-a, 2-c, 3-b, 4-d\n"
        "(D) 1-c, 2-d, 3-b, 4-a\n"
        "\n"
        "Ans - A\n"
        "\n"
        "Ref -  Cha. Indriya\n"
    )
    parsed, errors = parse_bulk(content)
    assert len(parsed) == 1, f"Expected 1 parsed, got {len(parsed)}, errors: {[e.message for e in errors]}"
    assert len(errors) == 0
    pq = parsed[0]
    assert pq.correct_index == 0
    assert pq.pretext is not None
    assert "प्राकृत वर्ण" in pq.pretext
    assert pq.reference is not None


def test_parse_bulk_matching_with_regular_question():
    content = (
        "Q. Match the following with respective संख्या\n"
        "\n"
        "1) प्राकृत वर्ण           a) 4 \n"
        "2) स्वप्न                    b) 7 \n"
        "3) छाया                   c) 5 \n"
        "4) प्रकृति                 d) 6\n"
        "\n"
        "(A) 1-a, 2-b, 3-c, 4-d\n"
        "(B) 1-c, 2-a, 3-b, 4-d\n"
        "(C) 1-a, 2-c, 3-b, 4-d\n"
        "(D) 1-c, 2-d, 3-b, 4-a\n"
        "\n"
        "Ans - A\n"
        "\n"
        "Ref -  Cha. Indriya\n"
        "\n"
        "Q2. What is the capital of France?\n"
        "(A) London\n"
        "(B) Paris\n"
        "(C) Berlin\n"
        "(D) Madrid\n"
        "Ans - B\n"
    )
    parsed, errors = parse_bulk(content)
    assert len(parsed) == 2, f"Expected 2 parsed, got {len(parsed)}, errors: {[e.message for e in errors]}"
    assert len(errors) == 0
    assert parsed[0].pretext is not None
    assert parsed[0].correct_index == 0
    assert parsed[1].pretext is None
    assert parsed[1].correct_index == 1


def test_parse_bulk_four_mixed_questions():
    content = (
        "Q. 29. Consider the following signs of death:\n"
        "1. Algor mortis (Cooling of the body)\n"
        "2. Livor mortis (Post-mortem staining)\n"
        "3. Rigor mortis (Stiffening of muscles)\n"
        'How many of the above are considered "early" signs of death?\n'
        "(A) Only one\n"
        "(B) Only two\n"
        "(C) All three\n"
        "(D) None\n"
        "Ans - C\n"
        "Reference - All three are considered early changes following death, occurring before the onset of putrefaction (which is a late sign). (Ref: Reddy's FMT)\n"
        " \n"
        "Q. 2. Consider the following live attenuated vaccines:\n"
        "1. BCG\n"
        "2. Yellow Fever\n"
        "3. Salk Polio Vaccine\n"
        "4. Measles\n"
        "How many of the above are Live Attenuated Vaccines?\n"
        "(A) Only one\n"
        "(B) Only two\n"
        "(C) Only three\n"
        "(D) All four\n"
        "Ans - C\n"
        "Reference - Only three are correct (BCG, Yellow Fever, Measles). Salk is a killed (inactivated) polio vaccine, whereas Sabin (OPV) is live. (Ref: Park's Textbook of PSM)\n"
        " \n"
        "Statement as per सुश्रुत regarding भग्न\n"
        "1.वेल्लते प्रकम्पमानम ---- वक्र\n"
        "2.आभुग्नमविमुक्तास्थि----कांड भग्न\n"
        " \n"
        "(A) 1 is \u2705, 2 is \u274c\n"
        "(B) 1 is \u274c, 2 is \u2705\n"
        "(C) Both are \u2705\u2705\n"
        "(D) Both are \u274c\u274c\n"
        " \n"
        "Ans\n"
        "C\n"
        "Both are corrrect\n"
        "Ref su nidana 15/10\n"
        " \n"
        "Q. Match the following with respective संख्या\n"
        " \n"
        "1) प्राकृत वर्ण           a) 4\n"
        "2) स्वप्न                    b) 7\n"
        "3) छाया                   c) 5\n"
        "4) प्रकृति                 d) 6\n"
        " \n"
        "(A) 1-a, 2-b, 3-c, 4-d\n"
        "(B) 1-c, 2-a, 3-b, 4-d\n"
        "(C) 1-a, 2-c, 3-b, 4-d\n"
        "(D) 1-c, 2-d, 3-b, 4-a\n"
        " \n"
        "Ans - A\n"
        " \n"
        "Ref -  Cha. Indriya\n"
    )
    parsed, errors = parse_bulk(content)
    assert len(parsed) == 4, (
        f"Expected 4 parsed, got {len(parsed)}, "
        f"errors: {[e.message for e in errors]}"
    )
    assert parsed[0].correct_index == 2
    assert "Algor mortis" in parsed[0].text
    assert parsed[1].correct_index == 2
    assert "BCG" in parsed[1].text
    assert parsed[2].correct_index == 2
    assert "सुश्रुत" in parsed[2].text
    assert parsed[3].correct_index == 0
    assert parsed[3].pretext is not None
    assert "प्राकृत वर्ण" in parsed[3].pretext
