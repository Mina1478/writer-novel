import os
import json
import logging
from typing import Dict, List, Optional
from locales.i18n import t

logger = logging.getLogger(__name__)

GENRES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "genres.json")

class GenreManager:
    """Quản lý các thể loại truyện và mô tả hướng dẫn viết"""
    
    _cached_genres = None
    _cached_mtime = 0
    
    @classmethod
    def get_default_genres(cls) -> List[Dict[str, str]]:
        """Lấy danh sách thể loại mặc định nếu chưa có file"""
        # Mặc định sử dụng danh sách cũ từ file ngôn ngữ
        default_names = t("create.genres")
        if isinstance(default_names, str):
            default_names = ["Huyền huyễn tiên hiệp", "Đô thị ngôn tình", "Khoa học viễn tưởng", "Võ hiệp", "Trinh thám", "Lịch sử", "Quân sự", "Game", "Kinh dị", "Xuyên không - Trọng sinh", "Hệ thống", "Đồng nhân", "Mạt thế", "Điền văn - Hài hước", "Cổ đại ngôn tình", "Kỳ ảo phương Tây", "Nữ cường", "Tổng tài", "Thanh xuân vườn trường", "Cung đấu", "Gia đấu", "Hồng hoang", "Ngôn tình võng du", "Đô thị dị năng", "Linh dị - Bí ẩn", "Đam mỹ", "Bách hợp", "Thám hiểm lăng mộ", "Dị giới đại lục", "Cổ đại làm ruộng", "Không gian Tùy thân", "ABO", "Ma cà rồng", "Cạnh kỹ - Thể thao", "Đồng nhân Anime", "Vô hạn lưu", "Khác"]
            
        default_genres = []
        for name in default_names:
            desc = ""
            if name == "Huyền huyễn tiên hiệp":
                desc = "Thế giới tu tiên rộng lớn, sức mạnh siêu phàm, phân chia nhiều cảnh giới rõ rệt. Cốt truyện thường xoay quanh hành trình thăng cấp, cướp đoạt cơ duyên, phi thăng tiên giới. Văn phong cần kỳ ảo, chú trọng miêu tả công pháp, pháp bảo, linh thú."
            elif name == "Đô thị ngôn tình":
                desc = "Bối cảnh hiện đại, đời sống thành thị, xoay quanh các mối quan hệ tình cảm, gia đình, công sở. Tập trung vào tâm lý nhân vật, tình huống đời thường, lãng mạn hoặc ngược luyến. Lời thoại tự nhiên, gần gũi thực tế."
            elif name == "Khoa học viễn tưởng":
                desc = "Lấy bối cảnh tương lai, vũ trụ, hoặc các thế giới với trình độ công nghệ/khoa học vượt bậc (AI, robot, du hành thời gian). Đòi hỏi sự logic, xây dựng hệ thống quy tắc công nghệ/vũ trụ chặt chẽ mang tính thuyết phục cao."
            elif name == "Võ hiệp":
                desc = "Thế giới giang hồ, ân oán tình thù, võ công cái thế. Nhấn mạnh vào tinh thần trượng nghĩa, môn phái, các chiêu thức võ thuật võ lâm. Văn phong cổ trang, miêu tả chiêu thức hoa mỹ, tiết tấu nhanh."
            elif name == "Trinh thám":
                desc = "Xoay quanh các vụ án bí ẩn, tội phạm và quá trình đi tìm lời giải, phá án. Yêu cầu tính logic cực cao, chuỗi manh mối đan xen, gây cấn, hồi hộp, tạo bất ngờ ở phút chót (plot twist)."
            elif name == "Lịch sử":
                desc = "Bối cảnh dựa trên các triều đại lịch sử có thật hoặc hư cấu dựa trên bối cảnh lịch sử. Xoay quanh quyền mưu, tranh đoạt thiên hạ, chiến tranh giữa các quốc gia, xây dựng thế lực. Đòi hỏi kiến thức lịch sử, chính trị, văn phong trang trọng, mang đậm tính sử thi."
            elif name == "Quân sự":
                desc = "Tập trung vào các đề tài chiến tranh, quân đội, vũ khí, và các chiến dịch quân sự. Nhân vật chính thường là quân nhân, nhà chiến lược. Yêu cầu tính logic, am hiểu về chiến thuật, vũ khí thực tế, miêu tả các trận đánh hoành tráng, khốc liệt."
            elif name == "Game":
                desc = "Bối cảnh trong môi trường game thực tế ảo hoặc thế giới game kết hợp đời thực (Võng du). Nhân vật chính đánh quái, thăng cấp, cày đồ, lập guild, tham gia e-sports hoặc tranh bá. Cần hệ thống chỉ số, kỹ năng, trang bị rõ ràng, nhịp độ giải trí nhanh."
            elif name == "Kinh dị":
                desc = "Cốt truyện rùng rợn, khai thác các yếu tố siêu nhiên, tâm linh, quái vật hoặc tâm lý học vặn vẹo. Bầu không khí tăm tối, u ám, miêu tả cảm giác sợ hãi tột độ của nhân vật để gây rùng mình cho người đọc."
            elif name == "Xuyên không - Trọng sinh":
                desc = "Nhân vật chính du hành thời gian, không gian đến một thế giới khác hoặc sống lại kiếp trước. Thường mang theo kiến thức hiện đại hoặc bám sát ký ức kiếp trước để thay đổi số phận, vả mặt kẻ thù, xây dựng lại cuộc đời."
            elif name == "Hệ thống":
                desc = "Nhân vật chính sở hữu một 'Hệ thống' (như một trí tuệ nhân tạo trong não) giao nhiệm vụ, thưởng phạt, cung cấp cửa hàng đổi vật phẩm, kỹ năng. Văn phong mang tính giải trí cao, nhịp độ nhanh, tập trung thăng cấp."
            elif name == "Đồng nhân":
                desc = "Truyện dựa trên bối cảnh, nhân vật của một tác phẩm gốc có sẵn (như Naruto, Harry Potter, v.v.). Nhân vật chính thường xuyên không vào thế giới gốc, thay đổi cốt truyện hoặc tương tác với nhân vật gốc."
            elif name == "Mạt thế":
                desc = "Bối cảnh tận thế, thảm họa zombie, thiên tai, hoặc biến dị sinh học. Con người đấu tranh sinh tồn, thế giới xuất hiện các dị năng giả. Nhấn mạnh sự tàn khốc của nhân tính, thiếu thốn vật tư và xây dựng căn cứ."
            elif name == "Điền văn - Hài hước":
                desc = "Tập trung vào cuộc sống thường nhật, trồng trọt, chăn nuôi, làm giàu hoặc gia đình êm ấm. Nhịp độ chậm rãi (slow-burn), nhẹ nhàng, thư giãn, pha trộn nhiều tình huống hài hước, dở khóc dở cười."
            elif name == "Cổ đại ngôn tình":
                desc = "Bối cảnh phong kiến, xoay quanh tình yêu nam nữ. Khai thác gia đấu (những mâu thuẫn gia tộc), cung đấu (tranh giành quyền lực chốn hậu cung) hoặc quyền mưu quyền thần. Lời thoại cổ kính, trang nhã."
            elif name == "Kỳ ảo phương Tây":
                desc = "Bối cảnh phương Tây thời Trung Cổ, có hiệp sĩ, phép thuật, elf, rồng, ma cà rồng... Hệ thống ma pháp và thế giới quan mang đậm nét thần thoại hoặc fantasy (như D&D, Warcraft)."
            elif name == "Nữ cường":
                desc = "Nữ chính có tính cách kiên cường, thông minh, độc lập, hoặc sở hữu sức mạnh vượt trội. Truyện thường tập trung vào quá trình tự vươn lên, phá bỏ định kiến, đối mặt kẻ thù mà không dựa dẫm vào nam chính."
            elif name == "Tổng tài":
                desc = "Xa hoa, tập trung vào nam chính là những chủ tịch (tổng tài) giàu có, lạnh lùng, quyền lực, cùng nữ chính thường có xuất thân thấp hơn hoặc có vướng mắc tình cảm phức tạp. Yếu tố sủng ngọt hoặc ngược luyến tình thâm thường được đẩy mạnh."
            elif name == "Thanh xuân vườn trường":
                desc = "Bối cảnh trường học, thanh xuân rực rỡ. Khai thác tình yêu tuổi học trò trong sáng, nhiệt huyết thanh xuân, tình bạn, vượt qua áp lực thi cử và những rung động đầu đời."
            elif name == "Cung đấu":
                desc = "Bối cảnh mưu mô xảo quyệt chốn hậu cung phong kiến. Các phi tần, hoàng hậu, cung nữ dùng trí tuệ, mưu kế triệt hạ lẫn nhau để tranh giành sủng ái và quyền lực. Bầu không khí căng thẳng, máu lạnh."
            elif name == "Gia đấu":
                desc = "Bối cảnh trong những gia tộc lớn thời phong kiến. Đấu tranh, kèn cựa giữa mẹ chồng nàng dâu, các phòng, các chị em gái để bảo vệ lợi ích và vị thế trong gia đình. Đòi hỏi logic cao trị gia."
            elif name == "Hồng hoang":
                desc = "Dựa trên hệ thống thần thoại Trung Hoa cổ đại (Bàn Cổ khai thiên, Nữ Oa tạo nhân,...). Hệ thống sức mạnh cực kỳ khổng lồ, bối cảnh cấp bậc thần thánh vô lượng kiếp quy mô vũ trụ."
            elif name == "Ngôn tình võng du":
                desc = "Kết hợp game online và tình cảm đời thực. Tuyến tình cảm phát triển song song trong thế giới ảo và đời thực, có sự kiện offline, PK, đấu giải giữa các bang phái đầy thú vị."
            elif name == "Đô thị dị năng":
                desc = "Bối cảnh xã hội hiện đại nhưng đan xen những con người sở hữu năng lực đặc biệt (dị năng), tổ chức ngầm, hoặc yêu quái ẩn mình. Đòi hỏi sự kết hợp cân bằng giữa đời sống thực và thế giới huyền bí."
            elif name == "Linh dị - Bí ẩn":
                desc = "Xoay quanh tà ma, phong thủy, đạo sĩ trừ tà, hoặc những hiện tượng tâm linh không thể lý giải bằng khoa học. Không quá kinh dị tột độ mà chú trọng vào yếu tố huyền bí, hồi hộp khám phá sự thật."
            elif name == "Đam mỹ":
                desc = "Khai thác câu chuyện tình cảm sâu sắc, tinh tế hoặc ngang trái giữa hai nhân vật nam. Văn phong trau chuốt, chú trọng tâm lý, có thể lồng ghép mọi bối cảnh (cổ đại, hiện đại, mạt thế, tinh tế, v.v.)."
            elif name == "Bách hợp":
                desc = "Tập trung miêu tả tuyến tình cảm nhẹ nhàng, gắn bó hoặc mãnh liệt giữa hai nhân vật nữ. Duyên dáng, thiên về khai phá cảm xúc tinh tế, đồng cảm nội tâm, kết hợp nhiều bối cảnh khác nhau."
            elif name == "Thám hiểm lăng mộ":
                desc = "Hành trình trộm mộ, săn bảo vật ở các di tích cổ xưa chứa đầy cạm bẫy, cương thi, quái vật (như Đạo Mộ Bút Ký, Ma Thổi Đèn). Các chi tiết về đạo cụ, phong thủy, địa lý phải cực kỳ sống động và hấp dẫn."
            elif name == "Dị giới đại lục":
                desc = "Thế giới hoàn toàn hư cấu với bản đồ lục địa rộng lớn, có thể bao gồm kiếm thuật, ma pháp hoặc đấu khí. Tôn trọng luật rừng kẻ mạnh làm vua, mô phỏng các vương quốc, chủng tộc đa dạng tranh đấu."
            elif name == "Cổ đại làm ruộng":
                desc = "Một nhánh phụ của Điền văn nhưng nhấn mạnh vào bối cảnh cổ đại nghèo khó. Quá trình làm giàu chậm rãi từng bước từ hai bàn tay trắng, kinh doanh buôn bán, xây dựng gia đình no ấm."
            elif name == "Không gian Tùy thân":
                desc = "Nhân vật chính sở hữu một không gian bí mật (vòng tay, ngọc bội) có thể vào đó trồng trọt linh dược, chứa đồ, trữ nước thần, hoặc trốn tránh kẻ thù. Là bàn đạp lớn cho quá trình thăng cấp."
            elif name == "ABO":
                desc = "Bối cảnh Omegaverse (Alpha, Beta, Omega) với các đặc điểm sinh học và chất dẫn dụ đặc thù, thường lấy bối cảnh Tinh Tế (vũ trụ). Nhấn mạnh bản năng, sự kiểm soát, đánh dấu và các mối quan hệ tình cảm gai góc."
            elif name == "Ma cà rồng":
                desc = "Truyện xoay quanh sinh vật Ma cà rồng (Vampire), ma lang (Người sói), thợ săn. Thể hiện sự đấu tranh giữa bản năng khát máu và nhân tính, thường mang sắc thái lãng mạn tăm tối (Dark Romance)."
            elif name == "Cạnh kỹ - Thể thao":
                desc = "Nhiệt huyết thanh xuân, thi đấu e-sports hoặc các môn thể thao truyền thống (bóng rổ, điền kinh). Tôn vinh tinh thần đồng đội, nỗ lực luyện tập, vinh quang thi đấu, các chiến thuật đối kháng kịch tính."
            elif name == "Đồng nhân Anime":
                desc = "Viết dựa theo thế giới của các bộ Manga/Anime đình đám (One Piece, Pokemon, Bleach,...). Tương tác với các nhân vật được yêu thích, bổ sung những cái kết luyến tiếc hoặc tạo cuộc phiêu lưu hoàn toàn mới."
            elif name == "Vô hạn lưu":
                desc = "Nhân vật chính bị kéo vào một 'Không gian Chủ Thần', buộc phải xuyên qua nhiều thế giới (phim ảnh, game, ác mộng) để làm nhiệm vụ sinh tử, kiếm điểm nâng cấp. Nhịp độ dồn dập, hack não và nguy hiểm."
            elif name == "Khác":
                desc = "Các thể loại không nằm trong các phân loại chính, hoặc pha trộn nhiều yếu tố khác nhau (như Đồng nhân, Kỳ ảo phương Tây, Đam mỹ, Bách hợp, v.v.). AI cần linh hoạt kết hợp các yếu tố trong bối cảnh và yêu cầu riêng của tác giả để sáng tác cho phù hợp."
            
            default_genres.append({
                "name": name,
                "description": desc
            })
            
        return default_genres

    @classmethod
    def ensure_data_dir(cls):
        """Đảm bảo thư mục data tồn tại"""
        os.makedirs(os.path.dirname(GENRES_FILE), exist_ok=True)

    @classmethod
    def load_genres(cls) -> List[Dict[str, str]]:
        """Tải danh sách thể loại từ file (có cache theo mtime)"""
        cls.ensure_data_dir()
        if not os.path.exists(GENRES_FILE):
            default_genres = cls.get_default_genres()
            cls.save_genres(default_genres)
            return default_genres
            
        try:
            current_mtime = os.path.getmtime(GENRES_FILE)
            if cls._cached_genres is not None and cls._cached_mtime == current_mtime:
                return cls._cached_genres
            
            with open(GENRES_FILE, 'r', encoding='utf-8') as f:
                genres = json.load(f)
            cls._cached_genres = genres
            cls._cached_mtime = current_mtime
            return genres
        except Exception as e:
            logger.error(f"Error loading genres: {e}")
            return cls.get_default_genres()

    @classmethod
    def save_genres(cls, genres: List[Dict[str, str]]) -> bool:
        """Lưu danh sách thể loại xuống file"""
        cls.ensure_data_dir()
        try:
            with open(GENRES_FILE, 'w', encoding='utf-8') as f:
                json.dump(genres, f, ensure_ascii=False, indent=4)
            # Invalidate cache
            cls._cached_genres = genres
            cls._cached_mtime = os.path.getmtime(GENRES_FILE)
            return True
        except Exception as e:
            logger.error(f"Error saving genres: {e}")
            return False

    @classmethod
    def add_genre(cls, name: str, description: str = "") -> bool:
        """Thêm một thể loại mới"""
        genres = cls.load_genres()
        # Kiểm tra trùng tên
        if any(g["name"] == name for g in genres):
            return False
            
        genres.append({"name": name, "description": description})
        return cls.save_genres(genres)

    @classmethod
    def update_genre(cls, old_name: str, new_name: str, description: str) -> bool:
        """Cập nhật thông tin thể loại"""
        genres = cls.load_genres()
        for i, g in enumerate(genres):
            if g["name"] == old_name:
                # Nếu đổi tên, kiểm tra trùng tên mới
                if old_name != new_name and any(x["name"] == new_name for x in genres):
                    return False
                
                genres[i] = {"name": new_name, "description": description}
                return cls.save_genres(genres)
        return False

    @classmethod
    def delete_genre(cls, name: str) -> bool:
        """Xóa thể loại"""
        genres = cls.load_genres()
        initial_length = len(genres)
        genres = [g for g in genres if g["name"] != name]
        
        if len(genres) < initial_length:
            return cls.save_genres(genres)
        return False

    @classmethod
    def get_genre_names(cls) -> List[str]:
        """Lấy danh sách tên các thể loại để hiển thị UI"""
        genres = cls.load_genres()
        return [g["name"] for g in genres]
        
    @classmethod
    def get_genre_description(cls, name: str) -> str:
        """Lấy mô tả hướng dẫn của một thể loại"""
        genres = cls.load_genres()
        for g in genres:
            if g["name"] == name:
                return g["description"]
        return ""
