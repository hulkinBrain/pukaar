import re
import json
def data_extractor(text, mobile_number_string):

    if "from" in mobile_number_string:
        mobile_number = re.search(r'(\d+)(?=$)', mobile_number_string).group(1)
    else:
        mobile_number = None
        # print("Mobile number not found")

    if "name" in text:
        name = str(re.search('(?<=name)(.+?)(?=('
                             'qualification'
                             '|specialization|specialisation'
                             '|practice\stype|practise\stype'
                             '|area\sof\spractice|area\sof\spractise'
                             '|email'
                             '|query'
                             '|name'
                             '|$'
                             '))', text).group(1))
        name = name.strip().title() \
            if name.startswith(" ") and name.endswith(" ") else name

    else:
        name = None
        # print("name not found")

    if "qualification" in text:
        qualification = str(re.search('(?<=(qualification))(.+?)(?=('
                                      'specialization|specialisation'
                                      '|practice\stype|practise\stype'
                                      '|area\sof\spractice|area\sof\spractise'
                                      '|email'
                                      '|name'
                                      '|query'
                                      '|$'
                                      '))', text).group(2))
        qualification = qualification.strip().upper() \
            if qualification.startswith(" ") and qualification.endswith(" ") else qualification

    else:
        qualification = None
        # print("qualification not found")

    if "specialization" in text or "specialisation" in text:
        specialization = str(re.search('(?<=specialization|specialisation)(.+?)(?=('
                                       'qualification'
                                       '|practice\stype|practise\stype'
                                       '|area\sof\spractice|area\sof\spractise'
                                       '|email'
                                       '|name'
                                       '|query'
                                       '|$'
                                       '))', text).group(1))
        specialization = specialization.strip().upper() \
            if specialization.startswith(" ") and specialization.endswith(" ") else specialization

    else:
        specialization = None
        # print("specialization not found")

    if "practice type" in text or "practise type" in text:
        practice_type = str(re.search('(.+?)(?=('
                                      'qualification'
                                      '|specialization|specialisation'
                                      '|area\sof\spractice|area\sof\spractise'
                                      '|email'
                                      '|name'
                                      '|query'
                                      '|$'
                                      '))', text).group(1))
        if practice_type.strip().lower() == "public":
            practice_type = 1
        else:
            practice_type = 2

    else:
        practice_type = None
        # print("practice_type not found")

    if "area of practice" in text:
        area_of_practice = str(re.search('(?<=(area\sof\spractice|area\sof\spractise))(.+?)(?=('
                                         'qualification'
                                         '|specialization|specialisation'
                                         '|practice\stype|practise\stype'
                                         '|email'
                                         '|name'
                                         '|query'
                                         '|$'
                                         '))', text).group(2))
        area_of_practice = area_of_practice.strip().title() \
            if area_of_practice.startswith(" ") and area_of_practice.endswith(" ") else area_of_practice

    else:
        area_of_practice = None
        # print("area_of_practice not found")

    if "email" in text:
        email = str(re.search(r'[^\s](?<=email)(.+?)(?=('
                              'qualification|qualifications'
                              '|specialization|specialisation'
                              '|practice\stype|practise\stype'
                              '|area\sof\spractice|area\sof\spractise'
                              '|query'
                              '|name'
                              '|$'
                              '))', text).group(1))
        email_fixed = email
        email = re.sub('(\sat\s(?:((the\s)?(cost|rate)?(\sof)?))?)', '@', email_fixed)
        email = email.replace(" ", "").strip() \
            if email.startswith(" ") and email.endswith(" ") else email

    else:
        email = None
        # print("email not found")

    if "query" in text:
        query = str(re.search('(?<=query)(.+?)(?=('
                              'qualification|qualifications'
                              '|specialization|specialisation'
                              '|practice\stype|practise\stype'
                              '|email'
                              '|name'
                              '|area\sof\spractice|area\sof\spractise'
                              '|$'
                              '))', text).group(1))
        query = query.strip() \
            if query.startswith(" ") and (query.endswith(" ")) else query

    else:
        query = None
        # print("query not found")

    # print(name, qualification, specialization, practice_type, area_of_practice, email, query, mobile_number)

    return(dict({"name": dict({"value": name, "label": "Name"}),
                 "qualification": dict({"value": qualification, "label": "Qualification"}),
                 "specialization": dict({"value": specialization, "label": "Specialization"}),
                 "practice_type": dict({"value": practice_type, "label": "Practice Type"}),
                 "area_of_practice": dict({"value": area_of_practice, "label": "Area of Practice"}),
                 "email": dict({"value": email, "label": "Email"}),
                 "query": dict({"value": query, "label": "Query"}),
                 "mobile_number": dict({"value": mobile_number, "label": "Mobile number"})}))
