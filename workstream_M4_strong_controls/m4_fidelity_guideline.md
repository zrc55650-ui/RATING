# M4 改写保真标注指南(140 条,单人独立盲标)

## 任务

每条包含:题目(Problem)、原始步骤(ORIGINAL STEP)、改写句(PARAPHRASE)。
判断改写句是否**完整保留了原句的语义内容**,四选一填入 `fidelity_label`:

- **faithful**:表达同一个数学主张;原句的所有信息(包括错误,如果有)都被保留,
  没有新增、删除或修正任何数学内容;
- **minor_deviation**:核心主张相同,但存在轻微增删(如补了一句显然的解释、
  丢了一个无关紧要的修饰),不改变该步骤在推理中的作用;
- **meaning_changed**:数学内容被改变——包括**修正了原句的错误**、引入新错误、
  改变结论、增删关键条件或推导;
- **uncertain**:两句话的等价性确实无法判断。

## 最重要的一条规则

**如果原句本身是错的,忠实的改写必须保留同样的错误。**
改写句悄悄把错误修正了 = `meaning_changed`,即使它"更正确"。
你的任务不是判断步骤对不对,只判断两句话是否说了同一件事。

## 其他规则

1. 独立完成,不与他人讨论;只依据 sheet 内文本判断;
2. `confidence_1to5`:1=非常不确定,5=非常确定;
3. `notes` 选填;判 `meaning_changed` 时请简述哪里变了;
4. 只填写 `fidelity_label`、`confidence_1to5`、`notes` 三列,不改动其他列;
5. 每完成 35 条休息一次。

## 材料与回传

- `m4_fidelity_sheet.csv`:填写用表(UTF-8,Excel/WPS/Numbers 可直接打开,
  保存时保持 CSV 格式);
- `m4_fidelity_sheet.html`:阅读视图,与 CSV 按 `annotation_id` 一一对应;
- 完成后只回传填好的 CSV。
