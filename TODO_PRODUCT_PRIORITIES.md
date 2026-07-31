# Uu Tien Can Sua De Dua Tool Thanh San Pham That

Ngay tao: 2026-06-17

## Ket Luan Nhanh

Tool co tiem nang lam san pham that, nhung hien tai hop nhat o muc MVP/internal tool. Neu dung noi bo cho team marketing thi da co gia tri. Neu muon demo cho khach hoac ban thanh SaaS, can uu tien lam muot UX, loc search tot hon va nang chat luong output.

## Uu Tien 1: Lam Che Do Nguoi Moi

Van de:
- Form hien co qua nhieu truong va nhieu thuat ngu marketing/AI.
- Nguoi moi de roi o cac muc nhu `Muc tieu noi dung`, `Giong thuong hieu`, `Tru cot uu tien`, `May tao noi dung`, `Model viet noi dung`.

Can lam:
- Them che do mac dinh `Nguoi moi`.
- Chi hien cac truong quan trong nhat:
  - Ban ban gi?
  - Ten shop/thuong hieu
  - Khach hang muc tieu
  - Thong so/dac diem bat buoc
  - Noi dau/nhu cau khach hang
  - Bang chung duoc phep dung
  - Muc tieu chien dich
  - Nhip dang muc tieu
- An cac truong nang cao vao expander `Tuy chon nang cao`.
- Them nut nhanh: `Tao lich 1 tuan cho nguoi moi`.

Tieu chi xong:
- Nguoi moi co the nhap 5-7 o va bam tao ket qua ma khong can hieu toan bo he thong.
- Form dau tien nhin gon hon ro ret.

## Uu Tien 2: Siet Chat Search Cong Khai

Van de:
- Search cho san pham quat tu dien van lan ket qua quat gia dung, quat tich dien, phong ngu, pin, mini.
- Co nguon lech nhung bi cham diem cao, lam nguoi dung nghi la dung.

Can lam:
- Them negative keywords cho nhom quat tu dien:
  - `quat tich dien`
  - `quat sac`
  - `phong ngu`
  - `gia dinh`
  - `pin`
  - `mini`
  - `quat cay`
  - `quat ban`
- Tang diem khi ket qua co:
  - `tu dien`
  - `electrical enclosure`
  - `cabinet cooling`
  - `panel fan`
  - `quat loc`
  - `thong gio tu dien`
  - `qua nhiet`
- Chi gan nhan `Nguon manh` khi co ca 2 nhom y:
  - nhom san pham: quat, tan nhiet, thong gio, lam mat
  - nhom ngu canh: tu dien, cabinet, enclosure, cong nghiep
- Hien canh bao ro voi nguon diem thap: `Nguon nay khong nen dua vao bai viet chinh`.

Tieu chi xong:
- Khi search `quat tu dien EA12038S`, cac ket qua quat gia dung khong con duoc cham cao.
- Ket qua tot nhat phai lien quan truc tiep den tu dien/lam mat tu dien.

## Uu Tien 3: Nang Module 24 May Tao Noi Dung

Van de:
- Module hien co hien du 24 card nhung nhieu card con la template/fallback.
- Hook dang kieu `Y tuong bai ...` nen chua co gia tri brainstorm that.
- CTA bi lap lai nhieu.

Can lam:
- Sua prompt `generate_machine_content_ideas` de moi card bat buoc co:
  - hook cu the cho san pham
  - y tuong bai dang co the viet ngay
  - outline 3 gach dau dong
  - CTA rieng cho tung may
  - goi y anh rieng
  - muc do uu tien: cao/vua/thap
- Khong yeu cau tao sau cho tat ca 24 may neu model yeu. Co the tao truoc 6 may uu tien, cac may con lai dung fallback tot hon.
- Them nut `Dung y tuong nay de tao caption` hoac it nhat `Copy brief y tuong`.

Tieu chi xong:
- Nhap `Quat gio tu dien EA12038S Master`, card Checklist phai ra noi dung kieu:
  - Hook: `Tu dien nong nhung chua chac do quat hong. Kiem tra 5 diem nay truoc khi thay.`
  - Outline: nguon dien, kich thuoc 120x120x38, huong gio, vi tri bat vit, luoi loc.
  - CTA: gui anh tem/quat cu de doi chieu.

## Uu Tien 4: Lam Caption Gan Voi Dang That Hon

Van de:
- Caption hien co dung duoc nhung can bien tap.
- Footer cong ty qua dai neu gan vao moi bai.
- Mot so bai lap lai cum thong tin ky thuat.
- Format checklist co luc bi dinh cau.

Can lam:
- Them tuy chon footer:
  - `Khong them footer`
  - `Footer ngan`
  - `Footer day du`
- Mac dinh dung `Footer ngan`.
- Rut gon hashtag con 4-6 hashtag.
- Trong prompt, yeu cau moi caption tranh lap CTA va lap danh sach thong so.
- Format checklist moi y mot dong ro rang.

Tieu chi xong:
- Caption co the copy dang Facebook/Instagram sau khi sua nhe.
- Binh quan moi bai khong bi qua dai vi footer.

## Uu Tien 5: Onboarding Va Giai Thich Trong UI

Van de:
- Tab `Cach dung` da tot hon, nhung trong tab chinh nguoi dung van co the bi roi.
- Nhieu muc can tooltip/caption ngan ngay tai cho.

Can lam:
- Them caption ngan duoi cac muc kho:
  - Muc tieu noi dung
  - Giong thuong hieu
  - Tru cot uu tien
  - May tao noi dung
  - AI search cong khai
- Them expander `Toi la nguoi moi, nen chon gi?` ngay trong tab Tao noi dung.
- Them preset:
  - `Dang 3-5 bai/tuan cho san pham moi`
  - `Keo inbox tu van`
  - `Xay dung uy tin cong ty`
  - `Lam noi dung kien thuc de luu`

Tieu chi xong:
- Nguoi dung khong can mo tab Cach dung van co the biet nen chon gi.

## Uu Tien 6: Luu Lich Va Do Hieu Qua

Van de:
- Tab Lich da duyet co gia tri, nhung can ro hon cho workflow lam viec voi sep/team.

Can lam:
- Them trang thai bai:
  - `Nhap`
  - `Da duyet`
  - `Da dang`
  - `Can sua`
- Them ngay dang du kien.
- Them bo loc theo trang thai/ngay/may tao noi dung.
- Them nut export Markdown dep de gui sep.

Tieu chi xong:
- Co the dung tab Lich da duyet nhu bang quan ly content tuan.

## Uu Tien 7: Chuan Bi Neu Muon Ban Thanh San Pham

Can co neu di xa hon MVP:
- Dang nhap/tai khoan.
- Luu du lieu cloud.
- Multi workspace/team.
- Template rieng theo nganh.
- Ket noi Meta Graph API de len lich/dang bai that.
- Co che review/approval.
- Billing neu lam SaaS.

Chua can lam ngay:
- Thanh toan.
- Dang bai tu dong.
- Dashboard nang cao.

## Checklist Ngay Mai Nen Lam Truoc

1. Siet search cho nhom quat tu dien.
2. Them che do/preset `Nguoi moi`.
3. Sua module 24 may de ra y tuong cu the hon.
4. Them tuy chon footer ngan/day du.
5. Them nut `Tao lich 1 tuan cho nguoi moi`.

## Ghi Chu San Pham

Positioning nen giu:

Tool khong chi la AI viet caption. Tool la tro ly van hanh noi dung B2B cho nganh dien cong nghiep: tu brief san pham -> research insight -> caption -> goi y anh -> lich dang -> do hieu qua.

